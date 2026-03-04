"""
GradSafe Defense Method
============================================
This Class achieves a defense method describe in the paper below.

Paper title: Defending LLMs against Jailbreaking Attacks via Backtranslation
Arxiv link: https://arxiv.org/abs/2402.13494
Source repository: https://github.com/xyq7/GradSafe
"""

from aisafetylab.models import LocalModel
from aisafetylab.defense.inference_defense.defender_texts import (
    SORRY_RESPONSE,
    SAFE_SET,
    UNSAFE_SET,
)
import torch
import torch.nn.functional as F
import ast
from telesafety_defense.base_factory import OutputDefender


class GradSafeDefender(OutputDefender):
    def __init__(
        self,
        unsafe_set=UNSAFE_SET,
        safe_set=SAFE_SET,
        threshold=0.0478,
        verbose=True,
        model=None,
        tokenizer=None,
        model_name="vicuna-7b-v1.5",
    ):
        self.unsafe_set = ast.literal_eval(unsafe_set)
        self.safe_set = ast.literal_eval(safe_set)
        self.threshold = threshold
        self.verbose = verbose
        self.model_name = model_name
        self.model = None
        if model is not None and tokenizer is not None:
            if isinstance(model, LocalModel):
                self.model = model
            else:
                self.model = LocalModel(model, tokenizer, model_name)

    def get_loss(self, message):
        """
        Calculate the loss (log likelihood) for the target LLM.

        Args:
            message (str): Input messages.

        Returns:
            Negative log likelihood loss
        """
        LL = self.model.evaluate_log_likelihood(messages=message, require_grad=True)
        NLL = -sum(LL) / len(LL)
        return NLL

    def find_critical_para(self):
        """
        Find critical parameters in the model.

        Returns:
            Gradient norms comparison, row and column cosine similarities
        """

        model = self.model.model

        # get unsafe/safe set
        unsafe_set = self.unsafe_set
        safe_set = self.safe_set

        model.train()
        assert model.training is True

        # Calculate the average of unsafe prompts gradients as reference
        gradient_norms_compare = {}

        for sample in unsafe_set:
            # Gradient for prompt paired with complaince response Sure
            optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
            basic_sample = [
                {"role": "user", "content": sample},
                {"role": "assistant", "content": "Sure"},
            ]

            optimizer.zero_grad()
            # get target llm loss for last message
            neg_log_likelihood = self.get_loss(basic_sample)
            neg_log_likelihood.backward()
            for name, param in model.named_parameters():
                if param.grad is not None:
                    if name not in gradient_norms_compare:
                        gradient_norms_compare[name] = param.grad
                    else:
                        gradient_norms_compare[name] += param.grad
        for name, param in gradient_norms_compare.items():
            gradient_norms_compare[name] /= len(unsafe_set)

        # Calculate the average of cosine similarities for unsafe prompts with the reference
        row_coss = {}
        col_coss = {}
        for sample in unsafe_set:
            # Gradient for prompt paired with complaince response Sure
            optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
            basic_sample = [
                {"role": "user", "content": sample},
                {"role": "assistant", "content": "Sure"},
            ]

            optimizer.zero_grad()

            # get target llm loss for last message
            neg_log_likelihood = self.get_loss(basic_sample)
            neg_log_likelihood.backward()

            for name, param in model.named_parameters():
                if param.grad is not None and ("mlp" in name or "self" in name):
                    grad_norm = param.grad.to(gradient_norms_compare[name].device)
                    row_cos = torch.nan_to_num(
                        F.cosine_similarity(
                            grad_norm, (gradient_norms_compare[name]), dim=1
                        )
                    )
                    col_cos = torch.nan_to_num(
                        F.cosine_similarity(
                            grad_norm, (gradient_norms_compare[name]), dim=0
                        )
                    )
                    if name not in row_coss:
                        row_coss[name] = row_cos
                        col_coss[name] = col_cos
                    else:
                        row_coss[name] += row_cos
                        col_coss[name] += col_cos
        for name, param in row_coss.items():
            row_coss[name] /= len(unsafe_set)
            col_coss[name] /= len(unsafe_set)

        # Calculate the average of cosine similarities for safe prompts with the reference
        safe_row_coss = {}
        safe_col_coss = {}
        for sample in safe_set:
            optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
            basic_sample = [
                {"role": "user", "content": sample},
                {"role": "assistant", "content": "Sure"},
            ]

            optimizer.zero_grad()

            # get target llm loss for last message
            neg_log_likelihood = self.get_loss(basic_sample)
            neg_log_likelihood.backward()

            for name, param in model.named_parameters():
                if param.grad is not None and ("mlp" in name or "self" in name):
                    grad_norm = param.grad
                    row_cos = torch.nan_to_num(
                        F.cosine_similarity(
                            grad_norm, (gradient_norms_compare[name]), dim=1
                        )
                    )
                    col_cos = torch.nan_to_num(
                        F.cosine_similarity(
                            grad_norm, (gradient_norms_compare[name]), dim=0
                        )
                    )
                    if name not in safe_row_coss:
                        safe_row_coss[name] = row_cos
                        safe_col_coss[name] = col_cos
                    else:
                        safe_row_coss[name] += row_cos
                        safe_col_coss[name] += col_cos

        for name, param in safe_row_coss.items():
            safe_row_coss[name] /= len(safe_set)
            safe_col_coss[name] /= len(safe_set)

        # Calculate the cosine similarity gaps for unsafe and safe prompts
        minus_row_cos = {}
        minus_col_cos = {}
        for name, param in row_coss.items():
            minus_row_cos[name] = row_coss[name] - safe_row_coss[name]
            minus_col_cos[name] = col_coss[name] - safe_col_coss[name]
        return gradient_norms_compare, minus_row_cos, minus_col_cos

    def log(self, tag, msg):
        """
        Log detailed information during the attack process.

        Args:
            tag (str): The label for the log message.
            msg (str): The log message.
        """
        if self.verbose:
            print("#" * 20)
            print(tag)
            print("#" * 20)
            print(msg)
            print()

    def response(self, unsafe_score, messages):
        """
        Decide whether to return a safe response based on the unsafe score.

        Args:
            unsafe_score (float): Unsafe score
            messages (str): Input messages

        Returns:
            str: Safe or unsafe response
        """
        self.model.model.eval()
        assert self.model.model.training is False

        if unsafe_score > self.threshold:
            return SORRY_RESPONSE
        else:
            messages = self.model.chat(messages=messages)
        return messages

    def defend(self, model, messages):
        # Ensure messages is in the correct format
        if isinstance(messages, str):
            messages = [
                {
                    "role": "user",
                    "content": messages,
                }
            ]

        self.model = model  # LocalModel
        model = self.model.model  # model

        # Find critical parameters in the model.
        gradient_norms_compare, minus_row_cos, minus_col_cos = self.find_critical_para()

        model.train()
        assert model.training is True, "Model should be in training mode."

        # Gradient for prompt paired with complaince response Sure
        optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
        basic_sample = [
            {"role": "user", "content": messages[-1]["content"]},
            {"role": "assistant", "content": "Sure"},
        ]
        optimizer.zero_grad()
        neg_log_likelihood = self.get_loss(basic_sample)
        neg_log_likelihood.backward()

        # Cosine similarities for safety-critical parameters
        cos = []

        for name, param in model.named_parameters():
            if param.grad is not None and ("mlp" in name or "self" in name):
                grad_norm = param.grad.to(gradient_norms_compare[name].device)
                row_cos = torch.nan_to_num(
                    F.cosine_similarity(grad_norm, (gradient_norms_compare[name]), dim=1)
                )
                col_cos = torch.nan_to_num(
                    F.cosine_similarity(grad_norm, (gradient_norms_compare[name]), dim=0)
                )
                ref_row = minus_row_cos[name]
                ref_col = minus_col_cos[name]
                cos.extend(row_cos[ref_row > 1].cpu().tolist())
                cos.extend(col_cos[ref_col > 1].cpu().tolist())

        unsafe_score = sum(cos) / len(cos)
        self.log(tag="unsafe_score", msg=unsafe_score)
        return self.response(unsafe_score, messages)
