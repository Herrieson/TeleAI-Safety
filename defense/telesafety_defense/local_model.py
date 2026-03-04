from typing import Dict, Optional

import torch
from fastchat.conversation import get_conv_template
from tqdm import trange
from transformers import GenerationConfig


class LocalModel:
    def __init__(self, model, tokenizer, model_name, generation_config=None):
        self.model = model
        self.tokenizer = tokenizer
        self.model_name = model_name
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.pos_to_token_dict = {
            v: k.replace("▁", " ") for k, v in self.tokenizer.get_vocab().items()
        }
        self.eos_token_ids = [self.tokenizer.eos_token_id]
        self.pad_token_id = self.tokenizer.pad_token_id

        try:
            _model_name = model_name
            if "vicuna" in model_name:
                _model_name = "vicuna_v1.1"
            self.conversation = get_conv_template(_model_name)
        except KeyError:
            pass

        if "llama-2" in model_name:
            self.conversation.sep2 = self.conversation.sep2.strip()

        if model_name == "zero_shot":
            self.conversation.roles = tuple(
                ["### " + r for r in self.conversation.template.roles]
            )
            self.conversation.sep = "\n"

        if isinstance(generation_config, GenerationConfig):
            generation_config = generation_config.to_dict()
        if generation_config is None:
            generation_config = {}
        self.generation_config = dict(generation_config)
        self.device = next(self.model.parameters()).device

    def __getattr__(self, name):
        try:
            return getattr(self.model, name)
        except AttributeError as err:
            raise AttributeError(
                f"{self.__class__.__name__} object has no attribute '{name}'"
            ) from err

    def generate(self, input_ids, gen_config=None, batch=False):
        if isinstance(input_ids, dict):
            input_ids = input_ids["input_ids"]
        elif isinstance(input_ids, list):
            input_ids = torch.tensor(input_ids, dtype=torch.long)
        input_ids = input_ids.to(self.model.device)

        if batch:
            raise NotImplementedError("Batch generation not implemented")

        if gen_config is None:
            gen_config = getattr(self.model, "generation_config", None)
        if gen_config is not None:
            if not hasattr(gen_config, "max_new_tokens") or gen_config.max_new_tokens is None:
                gen_config.max_new_tokens = 128

        attn_mask = torch.ones_like(input_ids).to(self.model.device)
        output_ids = self.model.generate(
            input_ids,
            attention_mask=attn_mask,
            generation_config=gen_config,
            pad_token_id=self.tokenizer.pad_token_id,
        )[0]
        return output_ids[input_ids.size(1) :]

    def apply_chat_template(self, messages):
        import copy

        if isinstance(messages, str):
            msgs = [{"role": "user", "content": messages}]
        else:
            msgs = copy.deepcopy(list(messages))

        prefill = msgs[-1]["role"] == "assistant"

        try:
            prompt = self.tokenizer.apply_chat_template(
                msgs, tokenize=False, add_generation_prompt=not prefill
            )
        except Exception:
            conversation = self.conversation.copy()
            tmp = msgs
            if tmp[-1]["role"] != "assistant":
                tmp = tmp + [{"role": "assistant", "content": None}]

            if tmp[0]["role"] == "system":
                conversation.set_system_message(tmp[0]["content"])
                tmp = tmp[1:]
            for msg in tmp:
                conversation.append_message(msg["role"], msg["content"])
            prompt = conversation.get_prompt()

        if self.tokenizer.bos_token and prompt.startswith(self.tokenizer.bos_token):
            prompt = prompt.replace(self.tokenizer.bos_token, "", 1)
        if self.tokenizer.bos_token and not prompt.startswith(self.tokenizer.bos_token):
            prompt = self.tokenizer.bos_token + prompt
        if prefill and self.tokenizer.eos_token and prompt.strip().endswith(self.tokenizer.eos_token):
            idx = prompt.rindex(self.tokenizer.eos_token)
            prompt = prompt[:idx].rstrip()
        return prompt

    def evaluate_log_likelihood(self, messages, require_grad=False):
        import copy

        if isinstance(messages, str):
            msgs = [{"role": "user", "content": messages}]
        else:
            msgs = copy.deepcopy(list(messages))
        if not msgs:
            raise ValueError("messages must contain at least one turn.")
        if require_grad:
            assert self.model.training is True

        prompt = self.apply_chat_template(msgs)
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)

        if len(msgs) > 1:
            prompt_dropped = self.apply_chat_template(msgs[:-1])
            inputs_dropped = self.tokenizer(prompt_dropped, return_tensors="pt").to(self.device)
            start_index = inputs_dropped.input_ids.shape[1]
        else:
            start_index = 1

        if require_grad:
            outputs = self.model(**inputs, labels=inputs["input_ids"])
        else:
            with torch.no_grad():
                outputs = self.model(**inputs, labels=inputs["input_ids"])

        log_probs = torch.log_softmax(outputs.logits, dim=-1)
        values = []
        for position in range(start_index, inputs.input_ids.shape[1]):
            token_id = inputs.input_ids[0, position]
            log_prob = log_probs[0, position - 1, token_id]
            values.append(log_prob if require_grad else log_prob.item())
        return values

    def batch_chat(self, batch_messages, batch_size=8, skip_special_tokens=True, **kwargs):
        prompts = [self.apply_chat_template(messages) for messages in batch_messages]
        responses = []
        temp_generation_config = dict(self.generation_config)
        temp_generation_config.update(kwargs)
        for i in trange(0, len(prompts), batch_size):
            batch_prompts = prompts[i : i + batch_size]
            inputs = self.tokenizer(
                batch_prompts,
                return_tensors="pt",
                padding=True,
                add_special_tokens=False,
            ).to(self.device)
            out = self.model.generate(**inputs, **temp_generation_config)
            for j, input_ids in enumerate(inputs["input_ids"]):
                response = self.tokenizer.decode(
                    out[j][len(input_ids) :], skip_special_tokens=skip_special_tokens
                )
                responses.append(response)
        return responses

    def chat(self, messages, use_chat_template=True, **kwargs):
        if isinstance(messages, str) and use_chat_template:
            messages = [{"role": "user", "content": messages}]
        prompt = self.apply_chat_template(messages) if use_chat_template else messages
        inputs = self.tokenizer([prompt], return_tensors="pt", add_special_tokens=False).to(self.device)

        temp_generation_config = dict(self.generation_config)
        temp_generation_config.update(kwargs)
        if "max_new_tokens" not in temp_generation_config:
            temp_generation_config["max_new_tokens"] = 512

        with torch.no_grad():
            out = self.model.generate(**inputs, **temp_generation_config)
        return self.tokenizer.decode(
            out[0][len(inputs["input_ids"][0]) :], skip_special_tokens=True
        )
