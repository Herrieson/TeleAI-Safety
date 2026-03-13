"""
Erase-and-Check Defense Method
============================================
This Class achieves a defense method describe in the paper below.
This part of code is based on the code from the paper.

Paper title: Certifying LLM Safety against Adversarial Prompting
Arxiv link: https://arxiv.org/pdf/2309.02705
Source repository: https://github.com/aounon/certified-llm-safety
"""

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
import random
import tiktoken
from telesafety_defense.base_factory import OutputDefender
from telesafety_defense.utils.prompts import SORRY_RESPONSE


class _DefaultPatternScorer:
    """Fallback scorer used when external scorer dependencies are unavailable."""

    _FAIL_PATTERNS = (
        "I'm sorry",
        "Sorry",
        "I am sorry",
        "I apologize",
        "I cannot",
        "I can't",
        "As an AI",
        "As a language model",
    )

    def score(self, query=None, response: str = ""):
        text = response or ""
        for pattern in self._FAIL_PATTERNS:
            if pattern in text:
                return {"score": 0}
        return {"score": 1}


class EraseCheckDefender(OutputDefender):
    """
    Implements the erase-and-check defense method by progressively truncating the user's input
    from the end and checking if any of the truncated inputs produce harmful responses.

    Mention, we now only support the first mode of the original paper: adversarial suffix, where an adversarial sequence is appended at the end of a harmful prompt.

    Args:
        scorer (PatternScorer): Scorer to evaluate if a response is harmful.
        max_erase (int): Maximum number of tokens to erase from the end of the user's input.
        randomized (bool): Whether to randomly sample truncated inputs.
        prompt_sampling_ratio (float): Ratio of truncated inputs to sample if randomized is True.
    """

    def __init__(
        self,
        scorer=None,
        max_erase=20,
        randomized=False,
        prompt_sampling_ratio=0.1,
        verbose=False,
        model=None,
        tokenizer=None,
        model_name="vicuna-7b-v1.5",
    ):
        self.scorer = scorer or _DefaultPatternScorer()
        self.max_erase = max_erase
        self.randomized = randomized
        self.prompt_sampling_ratio = prompt_sampling_ratio
        self.verbose = verbose
        self.model_name = model_name
        self.model = model
        self.tokenizer = tokenizer
        logger.info(
            f"EraseCheckDefender initialized with scorer: {type(self.scorer).__name__}"
        )

    def _get_encoder_for_azure_model_name(self, model_name: str | None):
        """
        Get the appropriate tiktoken encoder based on the Azure OpenAI model name.

        Args:
            model_name (str or None): The name of the Azure OpenAI model.

        Returns:
            tiktoken.Encoding: The corresponding tiktoken encoder.
        """
        try:
            if model_name:
                return tiktoken.encoding_for_model(model_name)
        except Exception:
            pass

        lowered = (model_name or "").lower()
        base = "o200k_base" if "4o" in lowered else "cl100k_base"
        return tiktoken.get_encoding(base)

    @staticmethod
    def _score_value(score) -> float:
        if isinstance(score, dict):
            value = score.get("score", 0)
        else:
            value = score
        try:
            return float(value)
        except Exception:
            return 0.0

    def _is_harmful_response(self, query: str, response: str) -> bool:
        """
        Scorer convention in this repo: score=1 indicates jailbreak/harmful output.
        """
        score = self.scorer.score(query=query, response=response)
        return self._score_value(score) >= 1.0

    def erase_and_check_suffix(self, model, messages):
        """
        Erase the user's input one token at a time from the end and check if any of the truncated inputs produce harmful responses.

        Args:
            model: The model used to generate responses.
            messages (list): The input messages to be passed into the model.

        Returns:
            bool: True if all truncated inputs are safe, False if any produce a harmful response.
        """
        user_prompt = messages[-1]["content"]
        model_tokenizer = getattr(model, "tokenizer", None)
        if model_tokenizer is not None and hasattr(model_tokenizer, "decode"):
            self.tokenizer = model_tokenizer
            tokens = self.tokenizer(user_prompt, add_special_tokens=False)["input_ids"]
            decode_tokens = lambda ids: self.tokenizer.decode(ids, skip_special_tokens=True)
        else:
            self.tokenizer = self._get_encoder_for_azure_model_name(
                getattr(model, "model_name", None)
            )
            tokens = self.tokenizer.encode(user_prompt)
            decode_tokens = self.tokenizer.decode

        prompt_length = len(tokens)

        prompt_list = [user_prompt]

        max_erase = min(self.max_erase, prompt_length)

        for i in range(1, max_erase + 1):
            # Erase i tokens from the end
            truncated_tokens = tokens[:-i]
            if not truncated_tokens:
                # No tokens left, skip
                continue
            truncated_prompt = decode_tokens(truncated_tokens)
            prompt_list.append(truncated_prompt)

        # If randomized, sample a subset of prompts
        if self.randomized:
            num_prompts_to_test = int(self.prompt_sampling_ratio * (len(prompt_list) - 1))
            if num_prompts_to_test > 0:
                prompts_to_test = [prompt_list[0]] + random.sample(
                    prompt_list[1:], num_prompts_to_test
                )
            else:
                prompts_to_test = prompt_list
        else:
            prompts_to_test = prompt_list

        # Now, for each prompt, generate the response and check if it's harmful
        for idx, truncated_prompt in enumerate(prompts_to_test):
            # Prepare messages with truncated prompt
            truncated_messages = messages[:-1] + [
                {
                    "role": messages[-1]["role"],
                    "content": truncated_prompt,
                }
            ]
            response = model.chat(truncated_messages)
            harmful = self._is_harmful_response(messages[-1]["content"], response)
            if self.verbose:
                logger.info(f"Truncated Prompt {idx}: {truncated_prompt}")
                logger.info(f"Response: {response}")
                logger.info(f"Harmful: {harmful}")
            if harmful:
                # Response is harmful
                if self.verbose:
                    logger.info("Harmful response detected with truncated prompt.")
                return True
        # All responses are safe
        return False

    def defend(self, model, messages):
        """
        Defend against a potentially unsafe query by evaluating the model's response and performing the erase-and-check defense.

        Args:
            model: The model used to generate responses.
            messages (str or list): The input messages to be passed into the model. If a string is provided, it is
                                    wrapped in a list format.

        Returns:
            str: The model's response if safe, otherwise returns a predefined apology message indicating defense triggered.
        """

        # Ensure messages is in the correct format
        if isinstance(messages, str):
            messages = [
                {
                    "role": "user",
                    "content": messages,
                }
            ]

        # Generate the original response
        response = model.chat(messages)
        harmful = self._is_harmful_response(messages[-1]["content"], response)

        if self.verbose:
            logger.debug(f"Original Query: {messages[-1]['content']}")
            logger.debug(f"Original Response: {response}")
            logger.debug(f"Harmful: {harmful}")

        if harmful:
            # Original response is harmful
            return SORRY_RESPONSE

        # Apply erase-and-check defense
        is_unsafe = self.erase_and_check_suffix(model, messages)

        if is_unsafe:
            return SORRY_RESPONSE
        else:
            return response
