"""
DRO Defense Method
============================================
This Class implements a defense method that adds safety reminders to input prompts.
This part of code is based on the code from AISafetyLab.

Paper title: DRO: Defensive Reward Optimization for Aligned Language Models
"""

import os
import json
import torch
import torch.nn as nn
from typing import Union
from loguru import logger
from safetensors import safe_open
from transformers import PreTrainedModel, PreTrainedTokenizer, PreTrainedTokenizerFast

from telesafety_defense.base_factory import InferenceDefender


class DRODefender(InferenceDefender):
    """
    Defender that adds a safety reminder to the input prompt using soft prompts.
    This is an InternalDefender that works within the model by modifying input embeddings.
    """
    
    def __init__(self, model, tokenizer, model_name, chat_template_path,system_prompt_type="default"):
        """
        Initialize DRO Defender.
        
        Args:
            model: The target model to defend
            tokenizer: The tokenizer for the model
            model_name: Name of the model for loading prompts
            system_prompt_type: Type of system prompt to use
        """
        self.model = model
        self.tokenizer = tokenizer
        self.model_name = model_name
        self.system_prompt_type = system_prompt_type
        self.chat_template_path = chat_template_path
        # Load trained soft prompts
        script_dir = os.path.dirname(os.path.abspath(__file__))
        prompt_path = os.path.join(
            script_dir, 
            f'dro/trained_prompts/{self.model_name}/type.all_length.{self.system_prompt_type}.safetensors'
        )
        
        # Set chat template if not present
        if tokenizer.chat_template is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            tokenizer.chat_template = open(chat_template_path).read().replace('    ', '').replace('\n', '')
            #print(tokenizer.chat_template)
        else:
            logger.info("Tokenizer already has chat_template; skip loading {}", chat_template_path)
        
        # Load soft prompt from safetensors
        with safe_open(prompt_path, framework='pt') as f:
            self.soft_prompt = f.get_tensor('soft_prompt')
        
        # Process soft prompt as word embeddings
        self.toker, self.new_input_embeddings = self.process_soft_prompt_as_word_embedding(
            model, tokenizer, self.soft_prompt
        )
        
        logger.info(f"DRODefender initialized for {model_name}")
    
    def prepend_sys_prompt(self, messages, prompt_length):
        messages = [{'role': 'system', 'content': ''.join([f'<soft_prompt_{i}>' for i in range(prompt_length)])}] + messages
        return messages
    
    def process_soft_prompt_as_word_embedding(
        self,
        model: PreTrainedModel,
        toker: Union[PreTrainedTokenizer, PreTrainedTokenizerFast],
        soft_prompt: torch.nn.Parameter
    ) -> nn.Module:
        # We embed soft prompt into input word embedding and safe it
        # When loaded later, simply call model.set_input_embeddings()
        config = model.config
        padding_idx = config.pad_token_id

        old_toker_size = len(toker)
        toker.add_tokens([f'<soft_prompt_{i}>' for i in range(soft_prompt.size(0))], special_tokens=True)
        new_toker_size = len(toker)

        old_input_embeddings = model.get_input_embeddings()
        embedding_dim = old_input_embeddings.embedding_dim
        old_num_embeddings = old_input_embeddings.num_embeddings
        new_num_embeddings = max(new_toker_size, old_num_embeddings)

        new_input_embeddings = nn.Embedding(new_num_embeddings, embedding_dim, padding_idx)
        new_input_embeddings.weight.data[:old_toker_size] = old_input_embeddings.weight.data[:old_toker_size]
        new_input_embeddings.weight.data[old_toker_size:new_toker_size] = soft_prompt.data.to('cpu')
        return toker, new_input_embeddings
    
    
    def defend(self, model, messages):
        """
        Apply defense by prepending safety reminder and generating response.
        
        Args:
            model: The model to defend
            messages: Input messages (can be string or list)
            
        Returns:
            Generated text after defense
        """
        # Get the actual model from wrapper if needed
        if hasattr(model, 'model'):
            model = model.model
        
        # Set input embeddings
        generation_config = getattr(model, 'generation_config', None)
        model.set_input_embeddings(
            self.new_input_embeddings.to(device=model.device, dtype=model.dtype)
        )
        
        # Convert string to messages format if needed
        if isinstance(messages, str):
            messages = [{'role': 'user', 'content': messages}]
        
        # Prepend system prompt with soft prompt
        messages = self.prepend_sys_prompt(messages, self.soft_prompt.size(0))
        
        # Apply chat template and tokenize
        input_text = self.toker.apply_chat_template(
            messages, 
            add_generation_prompt=True, 
            tokenize=False
        )
        #print(input_text)
        input_ids = torch.tensor(
            self.toker.convert_tokens_to_ids(self.toker.tokenize(input_text)),
            dtype=torch.long,
        ).unsqueeze(0).to(model.device)

        # Generate outputs using the model
        try:
            outputs = model.generate(
                input_ids,
                max_new_tokens=512,
                temperature=1.0,
                do_sample=False,
                pad_token_id=self.toker.pad_token_id if hasattr(self.toker, 'pad_token_id') else None
            )
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return "I apologize, but I cannot process this request."

        # Decode the generated output
        generated_texts = self.toker.decode(outputs[0][input_ids.size(1):], skip_special_tokens=True)
        print(generated_texts)
        return generated_texts
