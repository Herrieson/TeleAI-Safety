import os
import sys
from dataclasses import dataclass
from typing import Optional, Dict, Any

sys.path.append(os.getcwd())

from tqdm import tqdm
from dataset import AttackDataset
from utils import BaseAttackManager, ConfigManager, parse_arguments
from utils.message_builder import build_messages
from models import load_model


@dataclass
class AttackConfig:
    data_path: str
    data_offset: int = 0
    image_root_in: Optional[str] = None

    target_model_type: str = "openai"
    target_model_name: str = "gpt-4o-mini"
    target_model_path: str = ""

    api_key: Optional[str] = None
    base_url: Optional[str] = None
    azure_key: Optional[str] = None
    azure_url: Optional[str] = None
    grok_key: Optional[str] = None
    grok_url: Optional[str] = None

    target_max_n_tokens: int = 256
    target_temperature: float = 0.7
    target_top_p: float = 1.0

    target_system_prompt: Optional[str] = None

    res_save_path: Optional[str] = "./results/minimal_example.jsonl"


class MinimalExampleManager(BaseAttackManager):
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

    def attack(self):
        dataset = AttackDataset(
            self.config.data_path,
            subset_slice=self.config.data_offset,
            image_root_in=getattr(self.config, "image_root_in", None),
        )
        for example_idx, example in enumerate(tqdm(dataset, desc="MinimalExample Attacking")):
            base_record = dict(example)
            query = base_record.get("query") or base_record.get("prompt") or base_record.get("question")
            if not query:
                continue

            final_query = query
            input_message = build_messages(
                final_query,
                inputs=base_record.get("inputs"),
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
                    "query": query,
                    "final_query": final_query,
                    "response": response,
                }
            )
            self.save(record)


def main():
    args = parse_arguments()
    config_path = args.config_path or "./configs/minimal_example.yaml"
    config_manager = ConfigManager(config_path=config_path)
    manager = MinimalExampleManager.from_config(config_manager.config)
    manager.attack()


if __name__ == "__main__":
    main()
