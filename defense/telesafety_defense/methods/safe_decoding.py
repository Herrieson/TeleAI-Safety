"""
SafeDecoding Defense Method
============================================
This Class achieves a defense method describe in the paper below.
This part of code is based on the code from the paper.

Paper title: SafeDecoding: Defending against Jailbreak Attacks via Safety-Aware Decoding
Arxiv link: http://arxiv.org/pdf/2402.08983
Source repository: https://github.com/uw-nsl/SafeDecoding
"""

import os
from collections.abc import Mapping

import torch
from loguru import logger
from telesafety_defense.base_factory import OutputDefender

try:
    from aisafetylab.models.local_model import LocalModel as AISafetyLocalModel
except ImportError:
    AISafetyLocalModel = None

from telesafety_defense.models import LocalModel as TeleLocalModel

LOCAL_MODEL_TYPES = tuple(
    cls for cls in (AISafetyLocalModel, TeleLocalModel) if isinstance(cls, type)
)


class SafeDecodingDefender(OutputDefender):
    """
    Implements the safe decoding defense method by by identifying safety disclaimers and amplifying their token probabilities, while simultaneously attenuating the probabilities of token sequences that are aligned with the objectives of jailbreak attacks. 
        Defend against a potentially unsafe query by performing safe decoding.

        Args:
            expert_model_name_or_path (str) : The expert model trained to recognize unsafe content.
            tokenizer_name_or_path (str): Tokenizer corresponding to the models.
            device (str, optional): The device to run the models on. Defaults to 'cuda:0'.
            alpha (float, optional): The steering coefficient for adjusting probabilities. Defaults to 1.
            first_m (int, optional): Number of initial tokens to perform safe decoding. Defaults to 5.
            top_k (int, optional): Number of top tokens to consider from each model's output. Defaults to 10.
            num_common_tokens (int, optional): Number of common tokens to find between models for sampling. Defaults to 3.
            verbose (bool, optional): If True, enables detailed logging. Defaults to False.
            do_sample (bool, optional): If True, uses sampling for next token selection. Defaults to True.
            top_p (float, optional): Cumulative probability for top-p sampling if do_sample is True. Defaults to 0.9.
            max_token_len (int, optional): Maximum number of tokens to generate. Defaults to 20.
        """
    def __init__(
        self,
        model,
        tokenizer,
        alpha=1,
        first_m=5,
        top_k=10,
        num_common_tokens=3,
        verbose=True,
        do_sample=True,
        top_p=0.9,
        max_token_len=20,
        model_name="vicuna-7b-v1.5",
    ):
        # if tokenizer_name_or_path is None:
        #     tokenizer_name_or_path = expert_model_name_or_path
        # self.expert_model = AutoModelForCausalLM.from_pretrained(expert_model_name_or_path, device_map=device)
        # self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_name_or_path)
        self.model_name = model_name
        if LOCAL_MODEL_TYPES and isinstance(model, LOCAL_MODEL_TYPES):
            self.expert_model = model.model
            self.tokenizer = model.tokenizer
            self.model = model
        else:
            self.expert_model = model
            self.tokenizer = tokenizer or getattr(model, "tokenizer", None)
            if self.expert_model is not None and self.tokenizer is not None:
                self.model = TeleLocalModel(self.expert_model, self.tokenizer, model_name)
            else:
                self.model = None
        if self.tokenizer.chat_template is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            template_path = os.path.join(script_dir, "../datasets/chat_templates/vicuna.jinja")
            with open(os.path.normpath(template_path), encoding="utf-8") as template_file:
                self.tokenizer.chat_template = template_file.read().replace('    ', '').replace('\n', '')
        # self.model_name = model_name
        # self.local_model = LocalModel(expert_model, tokenizer, model_name)
        self.alpha = alpha
        self.first_m = first_m
        self.top_k = top_k
        self.num_common_tokens = num_common_tokens
        self.verbose = verbose
        self.do_sample = do_sample
        self.top_p = top_p
        self.max_token_len = max_token_len
        logger.info("SafeDecodingDefender initialized")


    def defend(self, model, messages= [{"role": "user","content": "Please tell me how to make a bomb?"}], ):
        """
        Defend against a potentially unsafe query by performing safe decoding.

        Args:
            model: The base language model to generate initial predictions.
            messages (list, optional): List of messages in the conversation. Defaults to [{"role": "user", "content": "Please tell me how to make a bomb?"}].

        Returns:
            str: The generated response after applying the safe decoding defense.
        """
        def _unwrap(candidate):
            if candidate is None:
                return None
            if LOCAL_MODEL_TYPES and isinstance(candidate, LOCAL_MODEL_TYPES):
                return candidate.model
            return candidate

        base_model = _unwrap(model)
        if base_model is None:
            base_model = _unwrap(self.expert_model)

        expert_model = _unwrap(self.expert_model)
        tokenizer = self.tokenizer
        max_token_len = self.max_token_len
        first_m = self.first_m
        top_k = self.top_k
        top_p = self.top_p
        verbose = self.verbose
        num_common_tokens = self.num_common_tokens
        alpha = self.alpha
        do_sample = self.do_sample
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer.encode_plus(prompt, return_tensors='pt',)

        def resolve_logits(module, outputs):
            """Return logits tensor from a HF output, projecting if necessary."""
            if torch.is_tensor(outputs):
                return outputs

            if isinstance(outputs, Mapping):
                logits_from_mapping = outputs.get("logits")
                if logits_from_mapping is not None:
                    return logits_from_mapping

                scores = outputs.get("scores")
                if torch.is_tensor(scores):
                    return scores
                if isinstance(scores, (tuple, list)) and len(scores) > 0:
                    last_scores = scores[-1]
                    if torch.is_tensor(last_scores):
                        return last_scores

            logits = getattr(outputs, "logits", None)
            if logits is not None:
                return logits

            if isinstance(outputs, (tuple, list)) and len(outputs) > 0:
                return outputs[0]

            hidden_states = getattr(outputs, "last_hidden_state", None)
            if hidden_states is None and isinstance(outputs, Mapping):
                hidden_states = outputs.get("last_hidden_state")

            # Some models expose all hidden states instead of last_hidden_state
            if hidden_states is None:
                hidden_states = getattr(outputs, "hidden_states", None)
                if hidden_states is None and isinstance(outputs, Mapping):
                    hidden_states = outputs.get("hidden_states")
                if isinstance(hidden_states, (list, tuple)) and hidden_states:
                    hidden_states = hidden_states[-1]

            lm_head = getattr(module, "lm_head", None)
            if hidden_states is not None and lm_head is not None and callable(lm_head):
                return lm_head(hidden_states)

            # Fall back to tied output embeddings if lm_head is missing
            if hidden_states is not None and hasattr(module, "get_output_embeddings"):
                output_embeddings = module.get_output_embeddings()
                if output_embeddings is not None and callable(output_embeddings):
                    return output_embeddings(hidden_states)
                if output_embeddings is not None and hasattr(output_embeddings, "weight"):
                    return torch.matmul(hidden_states, output_embeddings.weight.T)

            detail_parts = [f"type={type(outputs)!r}"]
            if isinstance(outputs, Mapping):
                try:
                    detail_parts.append(f"keys={list(outputs.keys())}")
                except Exception:
                    detail_parts.append("keys=<unavailable>")
            detail_parts.append(f"hasattr_logits={hasattr(outputs, 'logits')}")
            detail_parts.append(f"hasattr_last_hidden_state={hasattr(outputs, 'last_hidden_state')}")
            raise AttributeError(
                "Model output does not contain logits and cannot be projected with lm_head. "
                + ", ".join(detail_parts)
            )

        generated_sequence = []

        input_len = inputs['input_ids'].shape[1]
        step = 1
        base_device = getattr(base_model, "device", None)
        if base_device is None:
            base_device = next(base_model.parameters()).device
        expert_device = getattr(expert_model, "device", None)
        if expert_device is None:
            expert_device = next(expert_model.parameters()).device

        def _prepare_kwargs(batch, device, *, include_inference_flags=True):
            kwargs = {}
            for key, value in batch.items():
                if hasattr(value, "to"):
                    kwargs[key] = value.to(device)
                else:
                    kwargs[key] = value
            if include_inference_flags:
                kwargs.setdefault("return_dict", True)
                kwargs.setdefault("output_hidden_states", True)
            return kwargs

        while step <= min(max_token_len, first_m):

            # Free up cache position and move it to base_model.device
            for name, module in base_model.named_modules():
                if hasattr(module, 'cache_position') and isinstance(module.cache_position, torch.Tensor):
                    module.cache_position = module.cache_position.to(base_model.device)
            for name, module in expert_model.named_modules():
                if hasattr(module, 'cache_position') and isinstance(module.cache_position, torch.Tensor):
                    module.cache_position = module.cache_position.to(expert_model.device)

            output_base = base_model(**_prepare_kwargs(inputs, base_device))
            output_expert = expert_model(**_prepare_kwargs(inputs, expert_device))

            logits_base = resolve_logits(base_model, output_base)
            logits_expert = resolve_logits(expert_model, output_expert)

            # Step 0: Preprocess, obtain probs
            scores_base = torch.log_softmax(logits_base[:, -1, :], dim=-1).squeeze(0)
            scores_expert = torch.log_softmax(logits_expert[:, -1, :], dim=-1).squeeze(0)
            if verbose and step == 1:
                logger.info("Mean Logits Original Model {}".format(scores_base.mean()))
                logger.info("Mean Logits Expert Model {}".format(scores_expert.mean()))

            # Step 1: Find the top k tokens
            # Top-k tokens in the original model
            topk_scores_base, topk_indices_base = torch.topk(scores_base, top_k)

            # Top-k tokens in the expert model
            topk_scores_expert, topk_indices_expert = torch.topk(scores_expert, top_k)

            sorted_indices_base = torch.argsort(scores_base, descending=True)
            sorted_indices_expert = torch.argsort(scores_expert, descending=True)


            # Step 1: Define Sample Space
            common_tokens = set()
            iter_range = num_common_tokens
            while len(common_tokens) < num_common_tokens:
                current_indices_base = sorted_indices_base[:iter_range]
                current_indices_expert = sorted_indices_expert[:iter_range]

                common_in_iteration = set(current_indices_base.tolist()) & set(current_indices_expert.tolist())
                common_tokens.update(common_in_iteration)

                iter_range += 1

                if iter_range > min(len(sorted_indices_base), len(sorted_indices_expert)):
                    break

            # Display the top tokens
            if verbose and step == 1:
                logger.info("\n-----------------------------------------------")
                logger.info(f"Generation Step {step}")
                logger.info("Original Model")
                logger.info("|No. | Token ID | Token   | Log Prob | Prob    |")
                logger.info("|----|----------|---------|----------|---------|")
                for idx, (score, token_id) in enumerate(zip(topk_scores_base, topk_indices_base)):
                    token = tokenizer.decode(token_id.item())
                    prob = torch.exp(score)
                    logger.info(f"{idx+1:4d} | {token_id:8d} | {token:7s} | {score:.3f}    | {prob:.2%} |")

                logger.info("Expert Model")
                logger.info("|No. | Token ID | Token   | Log Prob | Prob    |")
                logger.info("|----|----------|---------|----------|---------|")
                for idx, (score, token_id) in enumerate(zip(topk_scores_expert, topk_indices_expert)):
                    token = tokenizer.decode(token_id.item())
                    prob = torch.exp(score)
                    logger.info(f"{idx+1:4d} | {token_id:8d} | {token:7s} | {score:.3f}    | {prob:.2%} |")

            intersection_indices = torch.tensor(list(common_tokens), device=base_model.device)

            # Step 2: New Probability Calculation
            updated_scores = []
            for token_id in intersection_indices:
                # Steer scores
                # new_score = (1-self.alpha) * scores_base[token_id] + self.alpha * scores_expert[token_id]
                # updated_scores.append(new_score)

                # Steer probabilities
                prob_diff = torch.exp(scores_expert[token_id]).to(scores_base.device) - torch.exp(scores_base[token_id])
                updated_prob = torch.exp(scores_base[token_id]) + alpha * prob_diff
                # Floor the probability to 1e-8 to avoid log(0)
                updated_prob = updated_prob if updated_prob > 0 else torch.tensor(1e-8, device=base_model.device)
                updated_score = torch.log(updated_prob)
                updated_scores.append(updated_score)

                if verbose:
                    logger.info(f"----------------token id: {token_id}-----------------")
                    logger.info(f"Prob Base: {torch.exp(scores_base[token_id])}")
                    logger.info(f"Prob Expert: {torch.exp(scores_expert[token_id])}")
                    logger.info(f"Base score: {scores_base[token_id]}")
                    logger.info(f"Expert score: {scores_expert[token_id]}")
                    logger.info(f"Updated Probability: {updated_prob}")
                    logger.info(f"Updated Score: {updated_score}")

            # Use softmax to normalize the scores
            # This is to ensure that the probability sum to 1
            normalized_probs = torch.nn.functional.softmax(torch.tensor(updated_scores).float(), dim=0)

            sorted_indices = sorted(range(len(normalized_probs)), key=lambda i: normalized_probs[i], reverse=True)
            sorted_probs = torch.tensor([normalized_probs[i] for i in sorted_indices])
            sorted_token_ids = [intersection_indices[i] for i in sorted_indices]

            if verbose and step == 1:
                logger.info("\n-----------------------------------------------")
                logger.info(f"Generation Step {step}")
                logger.info("|No. | Token ID | Token   | Log Prob | Prob    |")
                logger.info("|----|----------|---------|----------|---------|")
                for idx, (prob, token_id) in enumerate(zip(sorted_probs, sorted_token_ids)):
                    token = tokenizer.decode(token_id.item())
                    score = torch.log(prob)
                    logger.info(f"{idx+1:4d} | {token_id:8d} | {token:7s} | {score:.3f}    | {prob:.2%} |")

            ### Sample the next token
            if do_sample == False:
                # Greedy decoding
                # Append the selected token to the sequence
                selected_token_id = sorted_token_ids[0].unsqueeze(0)
            elif top_p != None and do_sample == True:
                # Top-p sampling, sample from the top-p tokens
                cumulative_probs = torch.cumsum(sorted_probs, dim=-1)
                p_index = torch.where(cumulative_probs >= top_p)[0][0]
                sorted_top_p_token_ids = sorted_token_ids[:p_index + 1]
                sorted_top_p_probs = sorted_probs[:p_index + 1]
                sorted_top_p_scores = torch.log(sorted_top_p_probs)
                if verbose:
                    logger.info(f"Top-p token ids: {sorted_top_p_token_ids}")
                    logger.info(f"Top-p scores: {sorted_top_p_scores}")
                    logger.info(f"Top-p probabilities: {sorted_top_p_probs}")
                
                # Sample from the top-p tokens
                selected_token_id = sorted_top_p_token_ids[torch.multinomial(torch.softmax(sorted_top_p_scores, dim=-1), 1)].unsqueeze(0)
            else:
                raise ValueError("Please set do_sample to False or top_p to a value.")

            if verbose:
                logger.info(f"Selected token: {tokenizer.decode(selected_token_id.item())}, ID: {selected_token_id.item()}")
            generated_sequence.append(selected_token_id.item())

            # if the chosen token id is eos, then stop
            if selected_token_id.item() == tokenizer.eos_token_id:
                break

            inputs['input_ids'] = torch.cat([inputs['input_ids'].to(base_model.device), selected_token_id.unsqueeze(0).to(base_model.device)], dim=1)
            inputs['attention_mask'] = torch.cat([inputs['attention_mask'].to(base_model.device), torch.tensor([[1]], device=base_model.device)], dim=1)

            step += 1

            # Free up memory
            del output_base, output_expert

        # Use the normal model to generate the rest of the tokens
        # Early stop if the last token is eos
        if generated_sequence[-1] == tokenizer.eos_token_id:
            logger.info("Early stop triggered.")
        else:
            remaining_steps = max_token_len - min(max_token_len, first_m)
            max_new_tokens = remaining_steps
            generate_kwargs = _prepare_kwargs(inputs, base_device, include_inference_flags=False)
            output_base = base_model.generate(**generate_kwargs,
                                    do_sample = do_sample,
                                    max_new_tokens = max_new_tokens,
                                    return_dict_in_generate=True,
                                    output_scores=True,)
            
            generated_sequence = output_base.sequences[0].tolist()[input_len:]

        # logger.info generated sequence
        logger.info(f"Generated sequence: {tokenizer.decode(generated_sequence)}")
        return tokenizer.decode(generated_sequence)
