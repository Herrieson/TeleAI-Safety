"""
SI Attack Method (merge1)
========================
Shuffle text and image patches to create adversarial inputs.
"""
import base64
import io
import os
import random
import sys
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

import numpy as np
from PIL import Image
from tqdm import tqdm

sys.path.append(os.getcwd())

from dataset import AttackDataset
from utils import BaseAttackManager, ConfigManager, parse_arguments
from utils.message_builder import build_messages
from models import load_model

"""
  总体思路
  “SI Attack” 的核心就是对文本和图像做随机打乱，制造对抗输入：

  - 文本：打乱词序
  - 图像：把图切成固定大小 patch，然后随机重排 patch

  关键流程

  1. 读数据：AttackDataset + data_offset
  2. 对每个样本重复 num_trials 次
  3. 文本处理：shuffle_sentence 随机打乱词序
  4. 图像处理：shuffle_image 将图像切成 patch_size 的方块并随机重排
  5. 生成新输入：
      - 文本用打乱后的 final_query
      - 图像用打乱后的图（转成 data URL）
  6. 调目标模型并保存结果

  输入

  - 需要 query/prompt/question 之一
  - 图像从 inputs 里解析（支持 image_rel + image_root_in，或者 image_path/images 等）

  输出

  - example_idx
  - trial_idx
  - query（原始）
  - final_query（打乱后的文本）
  - final_image（可选保存）
  - response
"""

def shuffle_sentence(sentence: str) -> str:
    words = sentence.split()
    random.shuffle(words)
    return " ".join(words)


def shuffle_image(image: Image.Image, patch_size: int) -> Image.Image:
    image_np = np.array(image)
    if image_np.ndim != 3:
        return image

    height, width = image_np.shape[:2]
    h_patches = height // patch_size
    w_patches = width // patch_size
    if h_patches == 0 or w_patches == 0:
        return image

    crop_h = h_patches * patch_size
    crop_w = w_patches * patch_size
    cropped = image_np[:crop_h, :crop_w, :]

    patches = []
    for i in range(h_patches):
        for j in range(w_patches):
            patch = cropped[
                i * patch_size:(i + 1) * patch_size,
                j * patch_size:(j + 1) * patch_size,
                :
            ]
            patches.append(patch)

    random.shuffle(patches)

    shuffled = cropped.copy()
    for i in range(h_patches):
        for j in range(w_patches):
            shuffled[
                i * patch_size:(i + 1) * patch_size,
                j * patch_size:(j + 1) * patch_size,
                :
            ] = patches[i * w_patches + j]

    if crop_h != height or crop_w != width:
        output = image_np.copy()
        output[:crop_h, :crop_w, :] = shuffled
        return Image.fromarray(output)

    return Image.fromarray(shuffled)


def image_to_data_url(image: Image.Image, fmt: str = "PNG") -> str:
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/{fmt.lower()};base64,{encoded}"


def _safe_name(text: Optional[str]) -> str:
    if not text:
        return "none"
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in text)
    return safe.strip("_") or "none"


def _build_output_filename(parts: List[str]) -> str:
    base = "_".join(_safe_name(p) for p in parts if p)
    if len(base) > 120:
        base = base[:80].rstrip("_") + "_" + str(abs(hash(base)) % (10**12))
    return base + ".png"


def resolve_image_path(inputs: Optional[Dict[str, Any]]) -> Optional[str]:
    if not isinstance(inputs, dict):
        return None

    image_rel = inputs.get("image_rel")
    image_root_in = inputs.get("image_root_in")
    if image_rel and image_root_in:
        candidate = os.path.join(image_root_in, image_rel)
        if os.path.exists(candidate):
            return candidate

    for key in ("image", "image_path", "source_image_path", "image_url", "images"):
        value = inputs.get(key)
        if isinstance(value, str) and os.path.exists(value):
            return value
        if isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, str) and os.path.exists(item):
                    return item

    return None


@dataclass
class AttackConfig:
    data_path: str
    data_offset: int = 0
    image_root_in: Optional[str] = None
    image_root_out: Optional[str] = None
    keep_transformed_images: bool = False

    target_model_type: str = "openai"
    target_model_name: str = "gpt-4o-mini"
    target_model_path: str = ""

    api_key: Optional[str] = None
    base_url: Optional[str] = None
    azure_key: Optional[str] = None
    azure_url: Optional[str] = None
    grok_key: Optional[str] = None
    grok_url: Optional[str] = None

    shuffle_text: bool = True
    shuffle_image: bool = True
    patch_size: int = 512
    num_trials: int = 10
    seed: Optional[int] = None

    target_system_prompt: Optional[str] = None
    target_max_n_tokens: int = 300
    target_temperature: float = 0.0
    target_top_p: float = 1.0

    res_save_path: Optional[str] = "results/SI_Attack.jsonl"


class SIAttackManager(BaseAttackManager):
    @classmethod
    def from_config(cls, config: Dict[str, Any]):
        if isinstance(config, dict):
            config = AttackConfig(**config)
        return cls(config)

    def __init__(self, config: AttackConfig):
        super().__init__(getattr(config, "res_save_path", None))
        self.config = config
        self.target_model = load_model(
            model_type=config.target_model_type,
            model_name=config.target_model_name,
            model_path=config.target_model_path,
            config=config,
        )

        if config.seed is not None:
            random.seed(config.seed)
            np.random.seed(config.seed)

    def _maybe_save_image(self, image: Image.Image, name_parts: List[str]) -> Optional[str]:
        if not self.config.keep_transformed_images or not self.config.image_root_out:
            return None
        os.makedirs(self.config.image_root_out, exist_ok=True)
        filename = _build_output_filename(name_parts)
        out_path = os.path.join(self.config.image_root_out, filename)
        image.save(out_path, format="PNG")
        return out_path

    def _shuffle_inputs(self, inputs: Optional[Dict[str, Any]], name_parts: List[str]) -> Dict[str, Any]:
        if not self.config.shuffle_image:
            return {"final_inputs": inputs, "final_image": None}

        image_path = resolve_image_path(inputs)
        if not image_path:
            return {"final_inputs": inputs, "final_image": None}

        try:
            image = Image.open(image_path).convert("RGB")
        except Exception:
            return {"final_inputs": inputs, "final_image": None}

        shuffled = shuffle_image(image, self.config.patch_size)
        data_url = image_to_data_url(shuffled)
        final_image_path = self._maybe_save_image(shuffled, name_parts)
        return {"final_inputs": {"images": [data_url]}, "final_image": final_image_path}

    def attack(self):
        subset_slice = slice(self.config.data_offset, None) if self.config.data_offset else None
        dataset = AttackDataset(
            self.config.data_path,
            subset_slice=subset_slice,
            image_root_in=getattr(self.config, "image_root_in", None),
        )

        for example_idx, example in enumerate(tqdm(dataset, desc="SI Attack")):
            base_record = dict(example)
            query = (
                base_record.get("query")
                or base_record.get("prompt")
                or base_record.get("question")
            )
            if not query:
                continue

            inputs = base_record.get("inputs")

            for trial_idx in range(max(1, self.config.num_trials)):
                final_query = shuffle_sentence(query) if self.config.shuffle_text else query
                image_name = None
                image_path = resolve_image_path(inputs)
                if image_path:
                    image_name = os.path.basename(image_path)
                shuffled = self._shuffle_inputs(
                    inputs,
                    name_parts=[str(example_idx + (self.config.data_offset or 0)), str(trial_idx), image_name],
                )
                final_inputs = shuffled["final_inputs"]
                final_image_path = shuffled["final_image"]

                input_message = build_messages(
                    final_query,
                    inputs=final_inputs,
                    system_prompt=self.config.target_system_prompt,
                )
                response = self.target_model.chat(
                    input_message,
                    max_tokens=self.config.target_max_n_tokens,
                    temperature=self.config.target_temperature,
                    top_p=self.config.target_top_p,
                )

                record = dict(base_record)
                record.update(
                    {
                        "example_idx": example_idx + self.config.data_offset,
                        "trial_idx": trial_idx,
                        "query": query,
                        "final_query": final_query,
                        "final_image": final_image_path,
                        "response": response,
                    }
                )
                self.save(record)


def main():
    args = parse_arguments()
    config_path = args.config_path or "./configs/SI_Attack.yaml"
    config_manager = ConfigManager(config_path=config_path)
    manager = SIAttackManager.from_config(config_manager.config)
    manager.attack()


if __name__ == "__main__":
    main()
