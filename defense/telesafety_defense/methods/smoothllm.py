"""
SmoothLLM Defense Method
============================================
This class implements a defense method described in the paper:
Paper title:SMOOTHLLM: Defending Large Language Models Against Jailbreaking Attacks
"""

from telesafety_defense.base_factory import OutputDefender
from telesafety_defense.utils import DictScorer
import random
import string
import numpy as np

try:
    from loguru import logger
except ImportError:
    import logging

    class _StdLoggerAdapter:
        def __init__(self, name: str):
            self._logger = logging.getLogger(name)

        @staticmethod
        def _format(msg, *args):
            if not args:
                return msg
            try:
                return msg.format(*args)
            except Exception:
                return f"{msg} | args={args}"

        def info(self, msg, *args):
            self._logger.info(self._format(msg, *args))

        def warning(self, msg, *args):
            self._logger.warning(self._format(msg, *args))

        def error(self, msg, *args):
            self._logger.error(self._format(msg, *args))

        def debug(self, msg, *args):
            self._logger.debug(self._format(msg, *args))

    logger = _StdLoggerAdapter(__name__)


class SmoothLLMDefender(OutputDefender):
    """
    Implements the SmoothLLM defense method by applying random perturbations to the user's input
    and using majority voting to decide if the input is safe.

    Args:
        scorer (PatternScorer): Scorer to evaluate if a response is harmful.
        pert_type (str): Type of perturbation to apply ('RandomSwapPerturbation', 'RandomPatchPerturbation', 'RandomInsertPerturbation').
        pert_pct (float): Percentage of the input to perturb.
        num_copies (int): Number of perturbed copies to generate.
        threshold (float): Threshold for the proportion of harmful outputs to decide if the input is harmful.
    """
    def __init__(
        self,
        model,
        model_name,
        tokenizer,
        scorer=None,
        pert_type='RandomSwapPerturbation',
        pert_pct=10.0,
        num_copies=10,
        batch_size=8,
        verbose=False
    ):
        self.model = model
        self.model_name = model_name
        self.tokenizer = tokenizer
        self.scorer = scorer or DictScorer()
        self.pert_type = pert_type
        self.pert_pct = pert_pct
        self.num_copies = num_copies
        self.perturbation_fn = self.get_perturbation_fn(pert_type, pert_pct)
        self.verbose = verbose
        self.batch_size = batch_size
        logger.info(
            f"SmoothLLMDefender initialized with scorer: {type(self.scorer).__name__}, "
            f"perturbation: {pert_type}, perturbation percentage: {pert_pct}, "
            f"number of copies: {num_copies}"
        )

    @staticmethod
    def _batch_chat_with_fallback(model, batch_messages, batch_size):
        if hasattr(model, "batch_chat"):
            try:
                responses = model.batch_chat(batch_messages, batch_size=batch_size)
                if len(responses) == len(batch_messages):
                    return responses
            except Exception:
                logger.warning("model.batch_chat failed in SmoothLLM; fallback to per-sample chat.")

        if not hasattr(model, "chat"):
            raise AttributeError("Provided model does not support chat/batch_chat interface.")
        return [model.chat(messages) for messages in batch_messages]

    def get_perturbation_fn(self, pert_type, pert_pct):
        if pert_type == 'RandomSwapPerturbation':
            return RandomSwapPerturbation(pert_pct)
        elif pert_type == 'RandomPatchPerturbation':
            return RandomPatchPerturbation(pert_pct)
        elif pert_type == 'RandomInsertPerturbation':
            return RandomInsertPerturbation(pert_pct)
        else:
            raise ValueError(f"Unknown perturbation type: {pert_type}")

    def defend(self, model, messages):
        """
        Defend against a potentially unsafe query by applying SmoothLLM defense.

        Args:
            model (LocalModel): The model used to generate responses.
            messages (str or list): The input messages to be passed into the model. If a string is provided, it is 
                                    wrapped in a list format.

        Returns:
            str: The model's response if safe, otherwise returns a predefined apology message indicating defense triggered.
        """
        
        # Ensure messages is in the correct format
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        
        # Get the user's prompt
        user_prompt = messages[-1]["content"]
        #print(user_prompt)
        # Generate perturbed prompts
        perturbed_prompts = []
        for _ in range(self.num_copies):
            perturbed_prompt = self.perturbation_fn(user_prompt)
            perturbed_prompts.append(perturbed_prompt)
        # Generate responses for each perturbed prompt
        perturbed_messages_list = []
        for perturbed_prompt in perturbed_prompts:
            perturbed_message = messages[:-1] + [{
                "role": messages[-1]["role"],
                "content": perturbed_prompt
            }]
            perturbed_messages_list.append(perturbed_message)
        #print(perturbed_messages_list)  
        responses = self._batch_chat_with_fallback(
            model, perturbed_messages_list, self.batch_size
        )
        are_copies_jailbroken = [self.scorer.score("", response)['score'] == 1 for response in responses]
        
        if self.verbose:
            for idx in range(self.num_copies):
                perturbed_prompt = perturbed_messages_list[idx]
                response = responses[idx]
                response_score = are_copies_jailbroken[idx]
                logger.debug(f"Perturbed Prompt {idx + 1}: {perturbed_prompt}")
                logger.debug(f"Response {idx + 1}: {response}")
                logger.debug(f"Response Score {idx + 1}: {response_score}")

        # Calculate the percentage of responses that are jailbroken
        jb_percentage = np.mean(are_copies_jailbroken)
        smoothLLM_jb = True if jb_percentage > 0.5 else False
        outputs_and_jbs = zip(responses, are_copies_jailbroken)
    
        if self.verbose:
            logger.debug(f"Jailbreak Percentage: {jb_percentage * 100:.2f}%")
            logger.debug(f"smoothLLM_jb: {smoothLLM_jb}")

        majority_outputs = [
            output for (output, jb) in outputs_and_jbs 
            if jb == smoothLLM_jb
        ]
        if majority_outputs:
            return random.choice(majority_outputs)
        if responses:
            return responses[0]
        return ""

class Perturbation:
    """Base class for random perturbations."""
    def __init__(self, q):
        self.q = q  # Percentage of the input to perturb
        self.alphabet = string.printable

class RandomSwapPerturbation(Perturbation):
    """Implementation of random swap perturbations."""
    def __call__(self, s):
        list_s = list(s)
        num_swaps = int(len(s) * self.q / 100)
        if num_swaps == 0:
            return s
        sampled_indices = random.sample(range(len(s)), num_swaps)
        for i in sampled_indices:
            list_s[i] = random.choice(self.alphabet)
        return ''.join(list_s)

class RandomPatchPerturbation(Perturbation):
    """Implementation of random patch perturbations."""
    def __call__(self, s):
        list_s = list(s)
        substring_width = int(len(s) * self.q / 100)
        if substring_width == 0:
            return s
        max_start = len(s) - substring_width
        if max_start <= 0:
            start_index = 0
        else:
            start_index = random.randint(0, max_start)
        sampled_chars = ''.join(random.choice(self.alphabet) for _ in range(substring_width))
        list_s[start_index:start_index + substring_width] = sampled_chars
        return ''.join(list_s)

class RandomInsertPerturbation(Perturbation):
    """Implementation of random insert perturbations."""
    def __call__(self, s):
        list_s = list(s)
        num_inserts = int(len(s) * self.q / 100)
        for _ in range(num_inserts):
            idx = random.randint(0, len(list_s))
            list_s.insert(idx, random.choice(self.alphabet))
        return ''.join(list_s)
