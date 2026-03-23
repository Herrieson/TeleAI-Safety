import os
import sys
sys.path.append(os.getcwd())

import logging
from dataclasses import dataclass
from typing import List, Optional

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
        self.df, self.source_col, self.target_col = self._load_mapping_df(prompt_file)
        self.norm_sources = self.df[self.source_col].astype(str).apply(self._normalize)
        self.stats = {
            "lookups": 0,
            "exact": 0,
            "contains": 0,
            "fallback": 0,
        }

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.strip().lower().split())

    @staticmethod
    def _load_mapping_df(prompt_file: str):
        # Preferred schema from optimized SCAV outputs.
        df = pd.read_csv(prompt_file)
        col_map = {str(col).strip().lower(): col for col in df.columns}
        if "original_instruction" in col_map and "best_instruction" in col_map:
            source_col = col_map["original_instruction"]
            target_col = col_map["best_instruction"]
            mapped = df[[source_col, target_col]].dropna()
            if mapped.empty:
                raise ValueError(f"SCAV mapping file has no valid rows: {prompt_file}")
            return mapped, source_col, target_col

        # Legacy compact schema: exactly two columns without headers.
        df_legacy = pd.read_csv(prompt_file, header=None)
        if df_legacy.shape[1] == 2:
            mapped = df_legacy[[0, 1]].dropna()
            if mapped.empty:
                raise ValueError(f"SCAV mapping file has no valid rows: {prompt_file}")
            return mapped, 0, 1

        raise ValueError(
            "Invalid SCAV prompt_file format. Expected columns "
            "`original_instruction,best_instruction` or a 2-column mapping CSV. "
            f"Got {df_legacy.shape[1]} columns from: {prompt_file}"
        )

    def _lookup(self, query: str) -> List[str]:
        self.stats["lookups"] += 1
        norm_query = self._normalize(query)

        exact_mask = self.norm_sources == norm_query
        exact = self.df.loc[exact_mask, self.target_col]
        if not exact.empty:
            self.stats["exact"] += 1
            return exact.astype(str).tolist()

        contains_mask = self.norm_sources.apply(lambda x: bool(x) and x in norm_query)
        contains = self.df.loc[contains_mask, self.target_col]
        if not contains.empty:
            self.stats["contains"] += 1
            return contains.astype(str).tolist()

        self.stats["fallback"] += 1
        return [query]

    def optimize(self, query: str) -> List[str]:
        prompts = [query]
        for _ in range(self.max_round):
            new_prompts: List[str] = []
            for p in prompts:
                new_prompts.extend(self._lookup(p))
            prompts = list(dict.fromkeys(new_prompts))
        return prompts

    def get_stats(self):
        return dict(self.stats)


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

        stats = self.optimizer.get_stats()
        lookups = stats["lookups"]
        fallback_rate = (stats["fallback"] / lookups) if lookups else 0.0
        logger.info(
            "SCAV lookup summary: lookups=%d exact=%d contains=%d fallback=%d fallback_rate=%.2f%%",
            lookups,
            stats["exact"],
            stats["contains"],
            stats["fallback"],
            fallback_rate * 100,
        )


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
