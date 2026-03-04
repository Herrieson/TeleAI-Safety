"""
DPS Defense Method
==================

Weak-to-strong multimodal defense:
1) strong model observes whole image,
2) weak observers inspect local views,
3) strong model revises final answer using local evidence.
"""

from __future__ import annotations

import base64
import io
import os
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Mapping, Sequence

import numpy as np
from PIL import Image

from telesafety_defense.base_factory import OutputDefender

SORRY_RESPONSE = "I'm sorry, but I cannot provide assistance or information on that topic."


SYSTEM_PROMPTS = {
    "normal": "You are a careful multimodal assistant.",
    "whole_observation": (
        "You analyze the full image and the question carefully. "
        "Avoid being distracted by non-subject content."
    ),
    "local_observation": (
        "You analyze local visual evidence only. "
        "Be objective and avoid unsupported speculation."
    ),
}


@dataclass
class DPSConfig:
    crop_mode: str = "auto_crop"
    local_views: int = 3
    summary_word_limit: int = 20
    random_seed: int | None = 7


class DPSDefender(OutputDefender):
    def __init__(
        self,
        crop_mode: str = "auto_crop",
        local_views: int = 3,
        summary_word_limit: int = 20,
        random_seed: int | None = 7,
    ) -> None:
        self.config = DPSConfig(
            crop_mode=crop_mode,
            local_views=local_views,
            summary_word_limit=summary_word_limit,
            random_seed=random_seed,
        )
        self.latest_trace: dict = {}
        if random_seed is not None:
            random.seed(random_seed)

    @staticmethod
    def _ensure_messages(payload: str | Sequence[Mapping]) -> List[Mapping]:
        if isinstance(payload, str):
            return [{"role": "user", "content": payload}]
        if isinstance(payload, Iterable):
            messages = list(payload)
            if not messages:
                raise ValueError("Empty messages provided to DPSDefender.")
            return messages
        raise TypeError(f"Unsupported messages type for DPSDefender: {type(payload)}")

    @staticmethod
    def _extract_text(content) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks: List[str] = []
            for part in content:
                if isinstance(part, str):
                    chunks.append(part)
                elif isinstance(part, Mapping):
                    if "text" in part:
                        chunks.append(str(part["text"]))
                    elif part.get("type") == "text":
                        chunks.append(str(part.get("text", "")))
            return " ".join(x for x in chunks if x).strip()
        if content is None:
            return ""
        return str(content)

    @staticmethod
    def _extract_image_path(content) -> str | None:
        if not isinstance(content, list):
            return None
        for part in content:
            if not isinstance(part, Mapping):
                continue
            if part.get("type") == "image_path":
                candidate = part.get("image_path") or part.get("path")
                if isinstance(candidate, str):
                    return candidate
            if part.get("type") == "image":
                candidate = part.get("path")
                if isinstance(candidate, str):
                    return candidate
            if part.get("type") == "image_url":
                image_url = part.get("image_url")
                if isinstance(image_url, str) and os.path.exists(image_url):
                    return image_url
                if isinstance(image_url, Mapping):
                    url = image_url.get("url")
                    if isinstance(url, str) and os.path.exists(url):
                        return url
        return None

    @staticmethod
    def _encode_image_data_url(image_path: str) -> str:
        ext = Path(image_path).suffix.lower().lstrip(".") or "jpeg"
        mime = "jpeg" if ext in {"jpg", "jpeg"} else ext
        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/{mime};base64,{image_b64}"

    def _build_user_content(self, prompt: str, image_path: str | None):
        if not image_path:
            return prompt
        data_url = self._encode_image_data_url(image_path)
        return [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]

    def _chat_with_system(
        self,
        model,
        system_prompt: str,
        user_prompt: str,
        image_path: str | None = None,
    ) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": self._build_user_content(user_prompt, image_path)},
        ]
        response = model.chat(messages)
        return self._extract_text(response).strip()

    @staticmethod
    def _center_crop(img: Image.Image) -> Image.Image:
        w, h = img.size
        left = w // 4
        top = h // 4
        right = left + w // 2
        bottom = top + h // 2
        return img.crop((left, top, right, bottom))

    @staticmethod
    def _random_crop(img: Image.Image) -> Image.Image:
        w, h = img.size
        ratio = random.uniform(0.25, 0.5)
        cw = max(1, int(w * ratio))
        ch = max(1, int(h * ratio))
        x = random.randint(0, max(0, w - cw))
        y = random.randint(0, max(0, h - ch))
        return img.crop((x, y, x + cw, y + ch))

    @staticmethod
    def _parse_boxes(text: str, width: int, height: int) -> List[List[int]]:
        pattern = r"\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]"
        boxes = []
        for l, t, r, b in re.findall(pattern, text):
            left = max(0, min(width, int(l)))
            top = max(0, min(height, int(t)))
            right = max(0, min(width, int(r)))
            bottom = max(0, min(height, int(b)))
            if right > left and bottom > top:
                boxes.append([left, top, right, bottom])
        return boxes

    def _auto_mask(self, model, image_path: str) -> Image.Image:
        img = Image.open(image_path).convert("RGB")
        w, h = img.size
        prompt = (
            f"Notice that image shape is [0, 0, {w}, {h}]. "
            "Return coordinates for suspicious text regions in format: "
            "{'obj1': [left, top, right, bottom], ...}. Directly output coordinates."
        )
        answer = self._chat_with_system(model, SYSTEM_PROMPTS["normal"], prompt, image_path=image_path)
        boxes = self._parse_boxes(answer, w, h)
        arr = np.array(img)
        for left, top, right, bottom in boxes:
            arr[top:bottom, left:right] = 0
        return Image.fromarray(arr)

    def _pil_to_temp_image(self, img: Image.Image, suffix: str = ".jpg") -> str:
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        filename = Path("/tmp") / f"dps_{random.randint(0, 10**9)}{suffix}"
        filename.parent.mkdir(parents=True, exist_ok=True)
        with open(filename, "wb") as f:
            f.write(buf.getvalue())
        return str(filename)

    def _prepare_local_views(self, model, image_path: str) -> List[str]:
        img = Image.open(image_path).convert("RGB")
        views: List[str] = []
        if self.config.crop_mode == "crop":
            return [self._pil_to_temp_image(self._center_crop(img))]
        if self.config.crop_mode == "random_crop":
            return [self._pil_to_temp_image(self._random_crop(img))]
        masked = self._auto_mask(model, image_path)
        views.append(self._pil_to_temp_image(masked))
        views.append(self._pil_to_temp_image(self._center_crop(img)))
        views.append(self._pil_to_temp_image(self._random_crop(img)))
        return views[: max(1, self.config.local_views)]

    @staticmethod
    def _word_count(text: str) -> int:
        return len(text.split())

    @staticmethod
    def _is_uncertain(text: str) -> bool:
        lowered = text.lower()
        markers = [
            "unable to determine",
            "cannot determine",
            "can't determine",
            "insufficient information",
            "not enough information",
            "unclear",
        ]
        return any(marker in lowered for marker in markers)

    def _compress_if_needed(self, model, text: str) -> str:
        if self._word_count(text) <= self.config.summary_word_limit:
            return text
        prompt = (
            f"Please summarize precisely in <= {self.config.summary_word_limit} words. "
            f"Content: {text}"
        )
        return self._chat_with_system(model, SYSTEM_PROMPTS["normal"], prompt)

    def defend(self, model, messages: str | Sequence[Mapping]) -> str:
        chat_messages = self._ensure_messages(messages)
        user_message = chat_messages[-1]
        instruction = self._extract_text(user_message.get("content", ""))
        image_path = self._extract_image_path(user_message.get("content"))

        if not instruction:
            return SORRY_RESPONSE
        if not image_path or not os.path.exists(image_path):
            return self._extract_text(model.chat(chat_messages)).strip()

        trace = {
            "instruction": instruction,
            "image_path": image_path,
            "crop_mode": self.config.crop_mode,
            "weak_observations": [],
        }
        try:
            initial_strong = self._chat_with_system(
                model, SYSTEM_PROMPTS["whole_observation"], instruction, image_path=image_path
            )
            trace["initial_response_strong"] = initial_strong
            local_views = self._prepare_local_views(model, image_path)
            for idx, view_path in enumerate(local_views):
                weak_answer = self._chat_with_system(
                    model, SYSTEM_PROMPTS["local_observation"], instruction, image_path=view_path
                )
                weak_desc = self._chat_with_system(
                    model,
                    SYSTEM_PROMPTS["local_observation"],
                    "Please provide an objective and detailed visual description of this local view.",
                    image_path=view_path,
                )
                weak_answer_simple = self._compress_if_needed(model, weak_answer)
                weak_desc_simple = self._compress_if_needed(model, weak_desc)
                chosen_obs = weak_answer_simple if not self._is_uncertain(weak_answer) else weak_desc_simple
                trace["weak_observations"].append(
                    {
                        "index": idx,
                        "view_path": view_path,
                        "weak_answer": weak_answer,
                        "weak_description": weak_desc,
                        "chosen_observation": chosen_obs,
                    }
                )

            obs_text = ", ".join(
                f"agent {i + 1}: {obs['chosen_observation']}"
                for i, obs in enumerate(trace["weak_observations"])
            )
            strong_analysis_prompt = (
                "Here are local observations from weak agents: "
                f"{obs_text}\n"
                "Re-check whether the first answer may be misled by non-subject content."
            )
            strong_analysis = self._chat_with_system(
                model, SYSTEM_PROMPTS["whole_observation"], strong_analysis_prompt
            )
            analysis_simple = self._compress_if_needed(model, strong_analysis)
            final_prompt = (
                f"Based on prior analysis: {analysis_simple}\n"
                "Avoid harmful, malicious, or unethical content. "
                "Provide the final detailed answer.\n"
                f"Question: {instruction}"
            )
            final_answer = self._chat_with_system(
                model, SYSTEM_PROMPTS["whole_observation"], final_prompt, image_path=image_path
            )
            trace["strong_analysis"] = strong_analysis
            trace["strong_analysis_simple"] = analysis_simple
            trace["strong_final"] = final_answer
            self.latest_trace = trace
            return final_answer.strip()
        except Exception:
            return self._extract_text(model.chat(chat_messages)).strip()
