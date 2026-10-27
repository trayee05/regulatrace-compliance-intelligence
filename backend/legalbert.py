"""Local, optional LEGAL-BERT-SMALL sentence representations.

The published checkpoint is pretrained for masked language modeling, not for
obligation classification or calibrated sentence similarity. We use masked mean
pooling as a transparent candidate-alignment signal and retain rule-based
constraint checks as the decision gate.
"""

from __future__ import annotations

import importlib.util
import os
from functools import lru_cache
from pathlib import Path

MODEL_ID = "nlpaueb/legal-bert-small-uncased"
MODEL_REVISION = "0e23f7a9a39f59768ea7e09766d8ee308580fb17"
MODEL_DIR = Path(__file__).resolve().parents[1] / ".regulatrace" / "models" / "legal-bert-small"
MAX_TOKENS = 256


def model_status() -> dict[str, str | bool]:
    if os.getenv("REGULATRACE_LEGALBERT", "auto").lower() in {"off", "false", "0"}:
        return {"state": "disabled", "ready": False, "modelId": MODEL_ID, "detail": "Disabled by REGULATRACE_LEGALBERT."}
    if not all(importlib.util.find_spec(name) for name in ("torch", "transformers")):
        return {"state": "setup-required", "ready": False, "modelId": MODEL_ID, "detail": "Install requirements-ml.txt and download the checkpoint."}
    if not (MODEL_DIR / "config.json").is_file() or not (MODEL_DIR / "vocab.txt").is_file() or not any(
        (MODEL_DIR / name).is_file() for name in ("model.safetensors", "pytorch_model.bin")
    ):
        return {"state": "setup-required", "ready": False, "modelId": MODEL_ID, "detail": "Download the Legal-BERT checkpoint with setup-legalbert.ps1."}
    return {"state": "ready", "ready": True, "modelId": MODEL_ID, "detail": "Local checkpoint available; inference loads on first use."}


@lru_cache(maxsize=1)
def _model_and_tokenizer():
    import torch
    from transformers import AutoModel, AutoTokenizer

    if not model_status()["ready"]:
        raise RuntimeError("The local Legal-BERT checkpoint is not ready.")
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True, use_fast=True)
    model = AutoModel.from_pretrained(MODEL_DIR, local_files_only=True)
    model.eval()
    return model, tokenizer


def similarity_matrix(left: list[str], right: list[str]) -> list[list[float]]:
    """Return raw cosine similarities for text pairs; values are not probabilities."""
    if not left or not right:
        return [[] for _ in left]
    import torch
    import torch.nn.functional as functional

    model, tokenizer = _model_and_tokenizer()
    unique = list(dict.fromkeys([*left, *right]))
    vectors = {}
    for start in range(0, len(unique), 12):
        batch = unique[start : start + 12]
        encoded = tokenizer(batch, padding=True, truncation=True, max_length=MAX_TOKENS, return_tensors="pt")
        with torch.inference_mode():
            hidden = model(**encoded).last_hidden_state
            mask = encoded["attention_mask"].unsqueeze(-1)
            pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
            normalized = functional.normalize(pooled, p=2, dim=1)
        vectors.update({text: vector for text, vector in zip(batch, normalized)})
    return [[round(float(torch.dot(vectors[a], vectors[b])), 4) for b in right] for a in left]


def install_checkpoint() -> None:
    """Download only the files needed for CPU inference into ignored local state."""
    from huggingface_hub import snapshot_download

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=MODEL_ID,
        revision=MODEL_REVISION,
        local_dir=MODEL_DIR,
        allow_patterns=["config.json", "vocab.txt", "tokenizer_config.json", "special_tokens_map.json", "pytorch_model.bin"],
    )
    _model_and_tokenizer()


if __name__ == "__main__":
    install_checkpoint()
    print(f"Legal-BERT ready: {MODEL_ID} at {MODEL_DIR}")
