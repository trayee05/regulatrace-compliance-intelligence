"""Optional local InLegalBERT encoder for Indian-law entity linking suggestions.

The published checkpoint is a pretrained encoder, not a fine-tuned NER model.
Its cosine score is advisory and never proves legal identity or a contradiction.
"""

from __future__ import annotations

import importlib.util
import os
from functools import lru_cache
from pathlib import Path

MODEL_ID = "law-ai/InLegalBERT"
MODEL_REVISION = "b5ecfed8ed6cf9d25a3cb8225a8c52f161f7401a"
MODEL_DIR = Path(__file__).resolve().parents[1] / ".regulatrace" / "models" / "inlegalbert"


def status() -> dict[str, str | bool]:
    if os.getenv("REGULATRACE_INLEGALBERT", "auto").lower() in {"off", "false", "0"}:
        return {"state": "disabled", "ready": False, "modelId": MODEL_ID, "detail": "Disabled by REGULATRACE_INLEGALBERT."}
    if not all(importlib.util.find_spec(name) for name in ("torch", "transformers")):
        return {"state": "setup-required", "ready": False, "modelId": MODEL_ID, "detail": "Install the optional ML runtime and InLegalBERT checkpoint."}
    if not all((MODEL_DIR / name).is_file() for name in ("config.json", "vocab.txt", "pytorch_model.bin")):
        return {"state": "setup-required", "ready": False, "modelId": MODEL_ID, "detail": "Run setup-neurosymbolic.ps1 to download InLegalBERT."}
    return {"state": "ready", "ready": True, "modelId": MODEL_ID, "detail": "Local InLegalBERT checkpoint available."}


@lru_cache(maxsize=1)
def _load():
    import torch
    from transformers import AutoModel, AutoTokenizer

    if not status()["ready"]:
        raise RuntimeError("InLegalBERT checkpoint is not ready.")
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True)
    model = AutoModel.from_pretrained(MODEL_DIR, local_files_only=True)
    model.eval()
    return model, tokenizer


def cosine(left: str, right: str) -> float:
    import torch
    import torch.nn.functional as functional

    model, tokenizer = _load()
    tokens = tokenizer([left, right], padding=True, truncation=True, max_length=128, return_tensors="pt")
    with torch.inference_mode():
        hidden = model(**tokens).last_hidden_state
        mask = tokens["attention_mask"].unsqueeze(-1)
        vectors = functional.normalize((hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1), p=2, dim=1)
    return round(float(torch.dot(vectors[0], vectors[1])), 4)


def install_checkpoint() -> None:
    from huggingface_hub import snapshot_download

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=MODEL_ID,
        revision=MODEL_REVISION,
        local_dir=MODEL_DIR,
        allow_patterns=["config.json", "vocab.txt", "tokenizer_config.json", "special_tokens_map.json", "pytorch_model.bin"],
    )
    _load()


if __name__ == "__main__":
    install_checkpoint()
    print(f"InLegalBERT ready: {MODEL_ID} at {MODEL_DIR}")
