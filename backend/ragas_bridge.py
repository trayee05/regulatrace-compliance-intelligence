"""Source-ID precision for expert-labeled retrieval evaluation.

Ragas' non-LLM IDBasedContextPrecision is used when installed. The exact
arithmetic fallback is explicitly labeled so a score never masquerades as a
Ragas run. A reference label set must be supplied by the evaluator.
"""

from __future__ import annotations

import importlib.util


async def score_source_ids(retrieved: list[str], reference: list[str]) -> dict[str, object]:
    if importlib.util.find_spec("ragas") is not None:
        try:
            from ragas import SingleTurnSample
            from ragas.metrics import IDBasedContextPrecision

            sample = SingleTurnSample(retrieved_context_ids=retrieved, reference_context_ids=reference)
            score = await IDBasedContextPrecision().single_turn_ascore(sample)
            return {"precision": round(float(score), 4), "backend": "ragas", "detail": "Ragas IDBasedContextPrecision evaluated the supplied source IDs."}
        except Exception as exc:
            return {"precision": 0.0, "backend": "error", "detail": f"Ragas evaluation failed ({type(exc).__name__}); no score is claimed."}
    expected = set(reference)
    score = sum(source_id in expected for source_id in retrieved) / len(retrieved) if retrieved else 0.0
    return {"precision": round(score, 4), "backend": "deterministic", "detail": "Ragas is not installed; exact ID precision is shown as an explicitly labeled baseline."}
