"""
JailDAM Defense Method
======================

Refactored from the standalone JailDAM inference script into a `methods`-style
defender with `defend(model, messages)`.
"""

from __future__ import annotations

import os
from typing import Iterable, List, Mapping, Sequence

import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

from telesafety_defense.base_factory import OutputDefender

SORRY_RESPONSE = "I'm sorry, but I cannot provide assistance or information on that topic."


class Autoencoder(nn.Module):
    def __init__(self, input_dim: int, latent_dim: int = 64):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Linear(128, latent_dim),
            nn.ReLU(),
        )
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 128),
            nn.ReLU(),
            nn.Linear(128, input_dim),
        )

    def forward(self, x):
        return self.decoder(self.encoder(x))


class MemoryNetwork(nn.Module):
    def __init__(
        self,
        clip_model: CLIPModel,
        concept_embeddings: torch.Tensor,
        device: str,
        embedding_dim: int = 768,
        num_classes: int = 14,
    ):
        super().__init__()
        self.clip_model = clip_model
        self.device = device
        self.embedding_dim = embedding_dim
        self.num_classes = num_classes
        self.memory_concepts = nn.Parameter(concept_embeddings)
        self.mlp = nn.Sequential(
            nn.Linear(1536, 512),
            nn.ReLU(),
            nn.Linear(512, self.num_classes),
        )

    def encode_text(self, input_ids, attention_mask):
        with torch.no_grad():
            return self.clip_model.get_text_features(
                input_ids=input_ids,
                attention_mask=attention_mask,
            )

    def encode_image(self, pixel_values):
        with torch.no_grad():
            return self.clip_model.get_image_features(pixel_values=pixel_values)

    def attention_memory_lookup(self, text_embedding, image_embedding):
        text_memory = self.memory_concepts
        image_memory = self.memory_concepts
        text_attention_scores = torch.matmul(text_embedding, text_memory.T)
        image_attention_scores = torch.matmul(image_embedding, image_memory.T)
        text_attention_weights = F.softmax(text_attention_scores, dim=-1)
        image_attention_weights = F.softmax(image_attention_scores, dim=-1)
        text_memory_output = torch.matmul(text_attention_weights, text_memory)
        image_memory_output = torch.matmul(image_attention_weights, image_memory)
        memory_output = torch.cat((text_memory_output, image_memory_output), dim=-1)
        return memory_output, text_attention_weights, image_attention_weights

    def forward(self, text_input_ids=None, text_attention_mask=None, image_pixel_values=None):
        if text_input_ids is not None and text_attention_mask is not None:
            text_embedding = self.encode_text(text_input_ids, text_attention_mask)
        else:
            text_embedding = torch.zeros(
                (image_pixel_values.shape[0], self.embedding_dim),
                device=self.device,
            )

        if image_pixel_values is not None:
            image_embedding = self.encode_image(image_pixel_values)
        else:
            image_embedding = torch.zeros(
                (text_input_ids.shape[0], self.embedding_dim),
                device=self.device,
            )

        memory_output, text_attention_weights, image_attention_weights = self.attention_memory_lookup(
            text_embedding, image_embedding
        )
        logits = self.mlp(memory_output)
        return logits, memory_output, text_embedding, image_embedding, text_attention_weights, image_attention_weights


class JailDAMDefender(OutputDefender):
    """
    JailDAM-based prompt detector wrapped as an OutputDefender.

    Args:
        checkpoint_path: Path to JailDAM detector checkpoint.
        threshold: Unsafe threshold on reconstruction error.
        clip_model_name: HuggingFace CLIP model name.
        fail_mode: "open" -> fall back to base model response if detector fails.
                   "closed" -> return SORRY_RESPONSE if detector fails.
    """

    def __init__(
        self,
        checkpoint_path: str = "",
        threshold: float = 123.9120,
        clip_model_name: str = "openai/clip-vit-large-patch14",
        fail_mode: str = "open",
        device: str | None = None,
    ) -> None:
        self.checkpoint_path = checkpoint_path
        self.threshold = threshold
        self.clip_model_name = clip_model_name
        self.fail_mode = fail_mode
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        self.loaded = False
        self.full_concept_embeddings: torch.Tensor | None = None
        self.clip_model: CLIPModel | None = None
        self.processor: CLIPProcessor | None = None
        self.memory_network: MemoryNetwork | None = None
        self.autoencoder: Autoencoder | None = None
        self.latest_score: float | None = None
        self.latest_trace: dict = {}

        self._load_detector()

    @staticmethod
    def _ensure_messages(payload: str | Sequence[Mapping]) -> List[Mapping]:
        if isinstance(payload, str):
            return [{"role": "user", "content": payload}]
        if isinstance(payload, Iterable):
            messages = list(payload)
            if not messages:
                raise ValueError("Empty messages provided to JailDAMDefender.")
            return messages
        raise TypeError(f"Unsupported messages type for JailDAMDefender: {type(payload)}")

    @staticmethod
    def _extract_text(content) -> str:
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, Mapping):
                    if "text" in item:
                        parts.append(str(item["text"]))
                    elif item.get("type") == "text":
                        parts.append(str(item.get("text", "")))
            return " ".join(x for x in parts if x).strip()
        return str(content).strip() if content is not None else ""

    def _extract_user_text(self, messages: Sequence[Mapping]) -> str:
        for message in reversed(messages):
            if isinstance(message, Mapping) and message.get("role") == "user":
                return self._extract_text(message.get("content", ""))
        return self._extract_text(messages[-1].get("content", ""))

    def _load_detector(self) -> None:
        if not self.checkpoint_path or not os.path.exists(self.checkpoint_path):
            self.loaded = False
            return

        checkpoint = torch.load(self.checkpoint_path, map_location=self.device)
        self.full_concept_embeddings = checkpoint["concept_embeddings"].to(self.device)

        self.clip_model = CLIPModel.from_pretrained(self.clip_model_name).to(self.device).eval()
        self.processor = CLIPProcessor.from_pretrained(self.clip_model_name)

        self.memory_network = MemoryNetwork(
            clip_model=self.clip_model,
            concept_embeddings=self.full_concept_embeddings[:, :768],
            device=self.device,
        ).to(self.device).eval()

        input_dim = self.full_concept_embeddings.shape[0] * 2
        self.autoencoder = Autoencoder(input_dim).to(self.device)
        self.autoencoder.load_state_dict(checkpoint["autoencoder_state_dict"])
        self.autoencoder.eval()

        self.loaded = True

    def _score_prompt(self, prompt: str) -> float:
        if not self.loaded:
            raise RuntimeError("JailDAM detector is not loaded.")
        if not self.processor or not self.memory_network or not self.autoencoder:
            raise RuntimeError("JailDAM detector components are missing.")
        if self.full_concept_embeddings is None:
            raise RuntimeError("Concept embeddings are not loaded.")

        image = Image.new("RGB", (224, 224), color="white")
        inputs = self.processor(
            text=[prompt],
            images=[image],
            return_tensors="pt",
            padding=True,
            truncation=True,
        ).to(self.device)

        with torch.no_grad():
            _, _, text_emb, img_emb, _, _ = self.memory_network.forward(
                text_input_ids=inputs["input_ids"],
                text_attention_mask=inputs["attention_mask"],
                image_pixel_values=inputs["pixel_values"],
            )
            sim_img = img_emb @ self.full_concept_embeddings[:, :768].T
            sim_txt = text_emb @ self.full_concept_embeddings[:, 768:].T
            features = torch.cat((sim_txt, sim_img), dim=-1)
            recon = self.autoencoder(features)
            recon_err = torch.mean((recon - features) ** 2, dim=-1)
            return float(recon_err.item())

    def _on_failure(self, model, messages):
        if self.fail_mode == "closed":
            return SORRY_RESPONSE
        if model is not None and hasattr(model, "chat"):
            return self._extract_text(model.chat(messages)).strip()
        return SORRY_RESPONSE

    def defend(self, model, messages: str | Sequence[Mapping]) -> str:
        """
        Defend a query by running JailDAM prompt detection before releasing output.

        Args:
            model: Model wrapper exposing `chat(messages)`.
            messages: User payload, either string or chat-style list.
        """
        chat_messages = self._ensure_messages(messages)
        query = self._extract_user_text(chat_messages)

        if not query:
            return SORRY_RESPONSE

        try:
            score = self._score_prompt(query)
            self.latest_score = score
            self.latest_trace = {
                "query": query,
                "score": score,
                "threshold": self.threshold,
                "detector_loaded": self.loaded,
            }
            if score >= self.threshold:
                return SORRY_RESPONSE
            return self._extract_text(model.chat(chat_messages)).strip()
        except Exception:
            return self._on_failure(model, chat_messages)
