import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

sys.path.append(os.getcwd())

import numpy as np
from tqdm import tqdm

from dataset import AttackDataset
from models import load_model
from utils import BaseAttackManager, ConfigManager, parse_arguments
from utils.message_builder import build_messages


@dataclass
class AttackConfig:
    data_path: str
    data_offset: int = 0
    image_root_in: Optional[str] = None
    max_examples: Optional[int] = None

    target_model_type: str = "openai"
    target_model_name: str = "gpt-4o-mini"
    target_model_path: str = ""

    api_key: Optional[str] = None
    base_url: Optional[str] = None
    azure_key: Optional[str] = None
    azure_url: Optional[str] = None
    azure_api_version: Optional[str] = None
    grok_key: Optional[str] = None
    grok_url: Optional[str] = None

    target_system_prompt: Optional[str] = None
    target_max_n_tokens: int = 512
    target_temperature: float = 0.0
    target_top_p: float = 1.0

    attention_model_path: str = ""
    attention_model_dtype: str = "bfloat16"
    attention_device_map: str = "auto"
    attention_layer: int = 18
    vision_token_id: int = 151655
    grid_dim: int = 28

    attention_block_size: int = 12
    attention_stride: int = 3
    attention_max_overlap: int = 40
    num_masks: int = 3
    mask_color: str = "green"

    keep_masked_images: bool = False
    image_root_out: Optional[str] = None

    res_save_path: Optional[str] = "./results/viscra.jsonl"


def _resolve_image_path(inputs: Optional[Dict[str, Any]]) -> Optional[str]:
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


def _load_pil_image(image_path: str):
    from PIL import Image

    return Image.open(image_path).convert("RGB")


def _find_top_blocks_with_stride(
    matrix: np.ndarray,
    block_size: int,
    stride: int,
    max_overlap: int,
    k: int,
) -> List[Tuple[int, int]]:
    rows, cols = matrix.shape
    integral = np.cumsum(np.cumsum(matrix, axis=0), axis=1)
    integral = np.pad(integral, ((1, 0), (1, 0)), mode="constant")

    candidates: List[Tuple[float, int, int]] = []
    for i in range(0, rows - block_size + 1, stride):
        for j in range(0, cols - block_size + 1, stride):
            total = (
                integral[i + block_size, j + block_size]
                - integral[i, j + block_size]
                - integral[i + block_size, j]
                + integral[i, j]
            )
            candidates.append((-float(total), i, j))

    candidates.sort()
    selected: List[Tuple[int, int]] = []
    for neg_total, x, y in candidates:
        conflict = False
        for sx, sy in selected:
            x_overlap = max(0, min(x + block_size, sx + block_size) - max(x, sx))
            y_overlap = max(0, min(y + block_size, sy + block_size) - max(y, sy))
            if x_overlap * y_overlap >= max_overlap:
                conflict = True
                break
        if conflict:
            continue
        selected.append((x, y))
        if len(selected) >= k:
            break
    return selected


class VisCRAManager(BaseAttackManager):
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
        self._attention_model = None
        self._attention_processor = None

    def _load_attention_model(self):
        if self._attention_model is not None:
            return
        if not self.config.attention_model_path:
            raise ValueError("attention_model_path is required for VisCRA.")

        import torch
        from transformers import AutoProcessor

        dtype = str(self.config.attention_model_dtype or "").lower()
        torch_dtype = None
        if dtype in ("bf16", "bfloat16"):
            torch_dtype = torch.bfloat16
        elif dtype in ("fp16", "float16"):
            torch_dtype = torch.float16
        elif dtype in ("fp32", "float32"):
            torch_dtype = torch.float32

        model = None
        try:
            from transformers import Qwen2_5_VLForConditionalGeneration

            model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                self.config.attention_model_path,
                torch_dtype=torch_dtype,
                device_map=self.config.attention_device_map,
                trust_remote_code=True,
            ).eval()
        except Exception:
            from transformers import AutoModelForCausalLM

            model = AutoModelForCausalLM.from_pretrained(
                self.config.attention_model_path,
                torch_dtype=torch_dtype,
                device_map=self.config.attention_device_map,
                trust_remote_code=True,
            ).eval()

        processor = AutoProcessor.from_pretrained(
            self.config.attention_model_path,
            trust_remote_code=True,
            padding_side="left",
            use_fast=True,
        )
        self._attention_model = model
        self._attention_processor = processor

    def _qwen_prepare_inputs(self, query: str, image_path: str):
        processor = self._attention_processor
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image_path},
                    {"type": "text", "text": f"{query} Answer:"},
                ],
            }
        ]
        prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

        image_inputs = [_load_pil_image(image_path)]
        inputs = processor(text=[prompt], images=image_inputs, padding=True, return_tensors="pt").to(
            self._attention_model.device
        )
        return inputs

    def _compute_attention_map(self, query: str, image_path: str) -> np.ndarray:
        import torch

        self._load_attention_model()
        inputs = self._qwen_prepare_inputs(query, image_path)

        with torch.no_grad():
            outputs = self._attention_model(**inputs, output_attentions=True)
        attentions = outputs.attentions
        layer = int(self.config.attention_layer)
        att = attentions[layer][0]

        input_ids = inputs["input_ids"][0]
        vision_token = int(self.config.vision_token_id)
        vision_positions = (input_ids == vision_token).nonzero(as_tuple=False).view(-1)
        if vision_positions.numel() == 0:
            raise ValueError("No vision tokens found for attention extraction.")
        image_token_start = int(vision_positions[0].item())
        image_token_end = int(vision_positions[-1].item())

        last_token_att = att[:, -1, image_token_start : image_token_end + 1].mean(0)
        vec = last_token_att.float().cpu().numpy()

        grid_dim = int(self.config.grid_dim) if self.config.grid_dim else 0
        expected = grid_dim * grid_dim if grid_dim else 0
        if expected == 0:
            guessed = int(np.sqrt(max(1, vec.shape[0])))
            grid_dim = max(1, guessed)
            expected = grid_dim * grid_dim
        if vec.shape[0] < expected:
            padded = np.zeros((expected,), dtype=np.float32)
            padded[: vec.shape[0]] = vec
            vec = padded
        if vec.shape[0] > expected:
            vec = vec[:expected]
        att2d = vec.reshape(grid_dim, grid_dim)
        return att2d

    def _mask_image(self, image_path: str, blocks: List[Tuple[int, int]], block_size: int) -> List[str]:
        from PIL import Image, ImageDraw

        img = Image.open(image_path).convert("RGB")
        out_paths: List[str] = []

        img_width, img_height = img.size
        grid_dim = int(self.config.grid_dim)
        px_per_cell_x = max(1, img_width // grid_dim)
        px_per_cell_y = max(1, img_height // grid_dim)

        should_keep = bool(self.config.keep_masked_images)
        if not should_keep:
            blocks = blocks[:1]

        out_root: Optional[str] = None
        base_name: Optional[str] = None
        if should_keep:
            out_root = self.config.image_root_out or os.path.join(
                os.path.dirname(self.config.res_save_path or "./results/viscra.jsonl"),
                "viscra_masks",
            )
            os.makedirs(out_root, exist_ok=True)
            base_name = os.path.splitext(os.path.basename(image_path))[0]

        for i, (row, col) in enumerate(blocks):
            masked_img = img.copy()
            draw = ImageDraw.Draw(masked_img)
            x0 = col * px_per_cell_x
            y0 = row * px_per_cell_y
            x1 = min(x0 + block_size * px_per_cell_x, img_width)
            y1 = min(y0 + block_size * px_per_cell_y, img_height)
            draw.rectangle((x0, y0, x1, y1), fill=self.config.mask_color)

            if should_keep and out_root and base_name:
                out_path = os.path.join(out_root, f"{base_name}_mask{i}.png")
            else:
                import tempfile

                tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                tmp.close()
                out_path = tmp.name

            masked_img.save(out_path, format="PNG")
            out_paths.append(out_path)

        return out_paths

    def attack(self):
        data_offset = getattr(self.config, "data_offset", 0) or 0
        subset_slice = slice(data_offset, None) if data_offset > 0 else None
        dataset = AttackDataset(
            self.config.data_path,
            subset_slice=subset_slice,
            image_root_in=getattr(self.config, "image_root_in", None),
        )

        for example_idx, example in enumerate(tqdm(dataset, desc="VisCRA Attacking")):
            if self.config.max_examples is not None and example_idx >= int(self.config.max_examples):
                break
            base_record = dict(example)
            query = base_record.get("query") or base_record.get("prompt") or base_record.get("question")
            if not query:
                continue

            inputs = dict(base_record.get("inputs") or {})
            image_path = _resolve_image_path(inputs)
            if not image_path:
                final_query = query
                messages = build_messages(
                    final_query,
                    inputs=inputs if inputs else None,
                    system_prompt=self.config.target_system_prompt,
                )
                response = self.target_model.chat(
                    messages,
                    max_tokens=self.config.target_max_n_tokens,
                    temperature=self.config.target_temperature,
                    top_p=self.config.target_top_p,
                )

                record = dict(base_record)
                record.update(
                    {
                        "example_idx": example_idx + data_offset,
                        "query": query,
                        "final_query": final_query,
                        "response": response,
                        "viscra_source_image": None,
                        "viscra_masked_image": None,
                        "viscra_blocks": [],
                    }
                )
                self.save(record)
                continue

            if not self.config.attention_model_path:
                grid_dim = max(1, int(self.config.grid_dim))
                block_size = max(1, int(self.config.attention_block_size))
                start = max(0, (grid_dim - block_size) // 2)
                blocks = [(start, start)]
            else:
                att2d = self._compute_attention_map(query, image_path)
                blocks = _find_top_blocks_with_stride(
                    att2d,
                    block_size=int(self.config.attention_block_size),
                    stride=int(self.config.attention_stride),
                    max_overlap=int(self.config.attention_max_overlap),
                    k=max(1, int(self.config.num_masks)),
                )
            masked_paths = self._mask_image(image_path, blocks, int(self.config.attention_block_size))
            chosen_mask = masked_paths[0] if masked_paths else image_path
            try:
                final_query = query
                msg_inputs = {"images": [chosen_mask]}
                messages = build_messages(
                    final_query,
                    inputs=msg_inputs,
                    system_prompt=self.config.target_system_prompt,
                )
                response = self.target_model.chat(
                    messages,
                    max_tokens=self.config.target_max_n_tokens,
                    temperature=self.config.target_temperature,
                    top_p=self.config.target_top_p,
                )
            finally:
                if (
                    chosen_mask
                    and (not self.config.keep_masked_images)
                    and chosen_mask != image_path
                    and os.path.exists(chosen_mask)
                ):
                    try:
                        os.remove(chosen_mask)
                    except Exception:
                        pass

            record = dict(base_record)
            record.update(
                {
                    "example_idx": example_idx + data_offset,
                    "query": query,
                    "final_query": final_query,
                    "response": response,
                    "viscra_source_image": image_path,
                    "viscra_masked_image": chosen_mask,
                    "viscra_blocks": blocks,
                }
            )
            self.save(record)


def main():
    args = parse_arguments()
    config_path = args.config_path or "./configs/viscra.yaml"
    config_manager = ConfigManager(config_path=config_path)
    manager = VisCRAManager.from_config(config_manager.config)
    manager.attack()


if __name__ == "__main__":
    main()
