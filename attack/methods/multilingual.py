"""
Multilingual Attack Method
============================================
This class implements a multilingual jailbreak method that uses translation
to bypass safety mechanisms in language models.
"""

import os
import sys
from typing import Optional, List, Dict, Any

# Add current working directory to path for relative imports
sys.path.append(os.getcwd())

from tqdm import tqdm
from loguru import logger
from dataclasses import dataclass

# Local imports
from dataset import AttackDataset
from utils import BaseAttackManager, ConfigManager, parse_arguments
from models import load_model
from logger import setup_logger
from mutation import Translate
from utils.message_builder import build_messages

@dataclass
class MultilingualConfig:
    """Configuration class for Multilingual attack parameters."""
    data_path: Optional[str] = None
    attack_data_path: Optional[str] = None
    data_offset: int = 0
    image_root_in: Optional[str] = None

    target_model_path: str = ""
    target_model_name: str = ""
    target_model_type: str = 'local'  # openai, azure, local
    model_type: Optional[str] = None  # backward-compatible alias
    mutation_method: str = 'zh-CN'
    system_prompt: str = 'You are a helpful assistant.'
    target_system_prompt: Optional[str] = None
    device: str = 'cuda'
    
    # API keys for different services
    api_key: str = ''  # OpenAI API key
    base_url: str = ''  # OpenAI base URL
    azure_key: str = ''  # Azure API key
    azure_url: str = ''  # Azure endpoint URL
    grok_key: str = ''  # Grok API key  
    grok_url: str = ''  # Grok endpoint URL

    target_max_n_tokens: int = 512
    target_temperature: float = 0.7
    target_top_p: float = 1.0
    
    res_save_path: Optional[str] = None
    log_path: Optional[str] = None


class TranslationHandler:
    """Handles multilingual translation mutations."""
    
    def __init__(self, config: MultilingualConfig) -> None:
        """Initialize translation handler with configuration."""
        self.config = config
        self.mutations = {
            # Chinese
            'zh-CN': Translate(language='zh-CN'),
            # Italian
            'it': Translate(language='it'),
            # Vietnamese
            'vi': Translate(language='vi'),
            # Arabic
            'ar': Translate(language='ar'),
            # # Korean
            # 'ko': Translate(language='ko'),
            # # Thai
            # 'th': Translate(language='th'),
            # # Bengali
            # 'bn': Translate(language='bn'),
            # # Swahili
            # 'sw': Translate(language='sw'),
            # # Javanese
            # 'jv': Translate(language='jv'),
        }
        
        if self.config.mutation_method not in self.mutations:
            raise ValueError(f"Unsupported mutation method: {self.config.mutation_method}")
            
        self.mutation = self.mutations[self.config.mutation_method]
        logger.info(f"Translation handler initialized for language: {self.config.mutation_method}")

    def mutate(self, query: str) -> List[str]:
        """Apply translation mutation to the query."""
        try:
            mutated_queries = self.mutation.translate(query)
            if isinstance(mutated_queries, str):
                mutated_queries = [mutated_queries]
            return mutated_queries
        except Exception as e:
            logger.error(f"Translation failed for query '{query}': {e}")
            return [query]  # Return original query if translation fails


class MultilingualManager(BaseAttackManager):
    """
    Main class for managing and executing Multilingual attacks.
    
    This attack method uses translation to different languages to create adversarial prompts
    that can potentially bypass safety mechanisms in language models.
    """
    
    def __init__(
        self,
        data_path: Optional[str] = None,
        attack_data_path: Optional[str] = "thu-coai/AISafetyLab_Datasets/harmbench_standard",
        data_offset: int = 0,
        image_root_in: Optional[str] = None,
        target_model_path: str = "lmsys/vicuna-7b-v1.5",
        target_model_name: str = "vicuna_1.5",
        target_model_type: str = 'local',
        model_type: Optional[str] = None,
        mutation_method: str = "zh-CN",
        system_prompt: str = "",
        target_system_prompt: Optional[str] = None,
        target_max_n_tokens: int = 512,
        target_temperature: float = 0.7,
        target_top_p: float = 1.0,
        device: str = "cuda",
        evaluator_type: str = 'pattern',
        evaluator_path: str = 'cais/HarmBench-Llama-2-13b-cls',
        res_save_path: str = "results/multilingual.jsonl",
        log_path: str = '../logs/',
        api_key: str = "",
        base_url: str = "",
        azure_key: str = "",
        azure_url: str = "",
        grok_key: str = "",
        grok_url: str = "",
        *args,
        **kwargs
    ):
        """Initialize the Multilingual attack manager."""
        super().__init__(res_save_path)

        # Create configuration object
        self.config = MultilingualConfig(
            data_path=data_path,
            attack_data_path=attack_data_path,
            data_offset=data_offset,
            image_root_in=image_root_in,
            target_model_path=target_model_path,
            target_model_name=target_model_name,
            target_model_type=target_model_type,
            model_type=model_type,
            mutation_method=mutation_method,
            system_prompt=system_prompt,
            target_system_prompt=target_system_prompt,
            target_max_n_tokens=target_max_n_tokens,
            target_temperature=target_temperature,
            target_top_p=target_top_p,
            device=device,
            api_key=api_key,
            base_url=base_url,
            azure_key=azure_key,
            azure_url=azure_url,
            grok_key=grok_key,
            grok_url=grok_url,
            res_save_path=res_save_path,
            log_path=log_path
        )

        # Initialize components
        self._initialize_components()
        
        # Setup logging
        if self.config.log_path:
            setup_logger(log_file_path=self.config.log_path)
        
        logger.info(f"Multilingual Manager initialized with {len(self.attack_dataset)} attack examples")
        logger.info(f"Using model type: {self._target_model_type()}")
        logger.info(f"Target model: {self.config.target_model_name}")
        logger.info(f"Translation language: {self.config.mutation_method}")

    def _target_model_type(self) -> str:
        return self.config.target_model_type or self.config.model_type or "local"

    def _resolve_data_path(self) -> str:
        data_path = self.config.data_path or self.config.attack_data_path
        if not data_path:
            raise ValueError("Missing dataset path: set `data_path` (or legacy `attack_data_path`).")
        return data_path
    
    def _initialize_components(self) -> None:
        """Initialize all components needed for the attack."""
        subset_slice = slice(self.config.data_offset, None) if self.config.data_offset else None
        self.attack_dataset = AttackDataset(
            self._resolve_data_path(),
            subset_slice=subset_slice,
            image_root_in=self.config.image_root_in,
        )
                
        # Initialize target model
        self.target_model = load_model(
            model_type=self._target_model_type(),
            model_name=self.config.target_model_name,
            model_path=self.config.target_model_path,
            config=self.config
        )
        
        # Initialize translation handler
        self.translation_handler = TranslationHandler(self.config)
        
    def generate_attack_prompt(self, raw_query: str) -> List[str]:
        """Generate attack prompts using translation."""
        return self.translation_handler.mutate(raw_query)
    
    def mutate(self, query: str) -> List[str]:
        """Generate mutated versions of the query using translation."""
        return self.generate_attack_prompt(query)
    
    def attack(self) -> None:
        """Execute the Multilingual attack on all examples in the dataset."""
        logger.info("Starting Multilingual attack...")
        
        for example_idx, example in enumerate(tqdm(self.attack_dataset, desc="Executing Multilingual attack")):
            try:
                base_record = dict(example)
                raw_query = (
                    base_record.get("query")
                    or base_record.get("prompt")
                    or base_record.get("question")
                    or base_record.get("instruction")
                )
                if not raw_query:
                    continue

                # Generate attack prompts
                mutated_queries = self.generate_attack_prompt(raw_query)
                
                for mutated_query in mutated_queries:
                    final_input = build_messages(
                        mutated_query,
                        inputs=base_record.get("inputs"),
                        system_prompt=self.config.target_system_prompt or self.config.system_prompt,
                    )
                    response = self.target_model.chat(
                        final_input,
                        max_tokens=self.config.target_max_n_tokens,
                        temperature=self.config.target_temperature,
                        top_p=self.config.target_top_p,
                    )
                    
                    result_data = dict(base_record)
                    result_data.update(
                        {
                            "example_idx": example_idx + self.config.data_offset,
                            "query": raw_query,
                            "final_query": mutated_query,
                            "response": response,
                            "mutation_method": self.config.mutation_method,
                        }
                    )
                    
                    self.save(result_data)
                    
            except Exception as e:
                logger.error(f"Error processing example {example_idx}: {e}")
                continue
        
        logger.info("Multilingual attack completed!")

    @classmethod
    def from_config(cls, config: Dict[str, Any], mutation_method: Optional[str] = None) -> 'MultilingualManager':
        """Create MultilingualManager from configuration dictionary."""
        config = config.copy()  # Avoid modifying original config
        if mutation_method is not None:
            config["mutation_method"] = mutation_method
        return cls(**config)


def main():
    """Main function to run the Multilingual attack."""
    try:
        # Parse command line arguments
        args = parse_arguments()
        config_path = args.config_path or './configs/multilingual.yaml'
        
        # Load configuration
        config_manager = ConfigManager(config_path=config_path)
        logger.info(f"Loaded configuration from: {config_path}")
        
        # Create and run attack manager
        attack_manager = MultilingualManager.from_config(config=config_manager.config)
        attack_manager.attack()
        
    except Exception as e:
        logger.error(f"Failed to run Multilingual attack: {e}")
        raise


if __name__ == "__main__":
    main()
