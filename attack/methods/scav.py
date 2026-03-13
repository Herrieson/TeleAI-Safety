import os
import sys
sys.path.append(os.getcwd())

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pandas as pd
from tqdm import tqdm

from dataset import AttackDataset
from models import load_model
from utils import BaseAttackManager, ConfigManager, parse_arguments
from utils.message_builder import build_messages

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@dataclass
class AttackConfig:
    data_path: str
    data_offset: int = 0
    image_root_in: Optional[str] = None

    target_model_type: str = "openai"
    target_model_path: str = ""
    target_model_name: str = ""
    target_system_prompt: Optional[str] = None

    api_key: Optional[str] = None
    base_url: Optional[str] = None
    azure_key: Optional[str] = None
    azure_url: Optional[str] = None
    grok_key: Optional[str] = None
    grok_url: Optional[str] = None

    target_max_n_tokens: int = 512
    target_temperature: float = 0.7
    target_top_p: float = 1.0

    prompt_file: Optional[str] = None
    optimized_file_8b: Optional[str] = None
    optimized_file_70b: Optional[str] = None
    max_round: int = 1
    res_save_path: Optional[str] = None


class ScavPromptOptimizer:
    def __init__(self, prompt_file: str, max_round: int = 1):
        self.prompt_file = prompt_file
        self.max_round = max_round
        self.df = pd.read_csv(prompt_file, header=None)

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.strip().lower().split())

    def _lookup(self, query: str) -> List[str]:
        norm_query = self._normalize(query)
        exact = self.df[self.df[0].astype(str).apply(self._normalize) == norm_query]
        if not exact.empty:
            return exact[1].astype(str).tolist()

        contains = self.df[self.df[0].astype(str).apply(self._normalize).apply(lambda x: x in norm_query)]
        if not contains.empty:
            return contains[1].astype(str).tolist()

        return [query]

    def optimize(self, query: str) -> List[str]:
        prompts = [query]
        for _ in range(self.max_round):
            new_prompts: List[str] = []
            for p in prompts:
                new_prompts.extend(self._lookup(p))
            prompts = list(dict.fromkeys(new_prompts))
        return prompts


class ScavManager(BaseAttackManager):
    @classmethod
    def from_config(cls, config):
        if isinstance(config, dict):
            config = AttackConfig(**config)
        return cls(config)

    def __init__(self, config: AttackConfig, delete_existing_res: bool = False):
        if isinstance(config, dict):
            config = AttackConfig(**config)
        super().__init__(config.res_save_path, delete_existing_res)
        self.config = config
        self.target_model = load_model(
            model_type=config.target_model_type,
            model_path=config.target_model_path,
            model_name=config.target_model_name,
            config=config,
        )
        self.optimizer = ScavPromptOptimizer(self._resolve_prompt_file(), max_round=config.max_round)

    def _resolve_prompt_file(self) -> str:
        prompt_file = self.config.prompt_file
        if not prompt_file:
            if "8b" in self.config.target_model_name.lower() and self.config.optimized_file_8b:
                prompt_file = self.config.optimized_file_8b
            else:
                prompt_file = self.config.optimized_file_70b
        if not prompt_file or not os.path.exists(prompt_file):
            raise FileNotFoundError(f"SCAV optimized prompt file not found: {prompt_file}")
        return prompt_file

    def attack(self):
        subset_slice = slice(self.config.data_offset, None) if self.config.data_offset else None
        attack_dataset = AttackDataset(
            self.config.data_path,
            subset_slice=subset_slice,
            image_root_in=self.config.image_root_in,
        )

        for idx, item in enumerate(tqdm(attack_dataset, desc="SCAV Attacking")):
            base_record = dict(item)
            query = (
                base_record.get("query")
                or base_record.get("prompt")
                or base_record.get("question")
                or base_record.get("content")
                or base_record.get("instruction")
            )
            if not query:
                continue

            optimized_prompts = self.optimizer.optimize(query)
            for opt_idx, opt_prompt in enumerate(optimized_prompts):
                final_query = query if opt_prompt == query else opt_prompt
                try:
                    input_messages = build_messages(
                        final_query,
                        inputs=base_record.get("inputs"),
                        system_prompt=self.config.target_system_prompt,
                    )
                    response = self.target_model.chat(
                        input_messages,
                        max_tokens=self.config.target_max_n_tokens,
                        temperature=self.config.target_temperature,
                        top_p=self.config.target_top_p,
                    )
                except Exception as e:
                    response = f"[Error] {e}"

                record = dict(base_record)
                record.update(
                    {
                        "example_idx": idx + self.config.data_offset,
                        "query": query,
                        "final_query": final_query,
                        "response": response,
                        "opt_index": opt_idx,
                    }
                )
                self.save(record)


def main():
    try:
        args = parse_arguments()
        config_path = args.config_path or "./configs/scav.yaml"
        config_manager = ConfigManager(config_path=config_path)
        logger.info(f"Loaded configuration from: {config_path}")

        attack_manager = ScavManager.from_config(config=config_manager.config)
        attack_manager.attack()

    except Exception as e:
        logger.error(f"Failed to run Scav attack: {e}")
        raise


if __name__ == "__main__":
    main()
