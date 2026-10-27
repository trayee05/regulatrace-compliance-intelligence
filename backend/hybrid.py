"""Orchestrate the deterministic baseline and local Legal-BERT signal."""

from __future__ import annotations

from typing import Any

from backend import legalbert
from backend.engine import compare_policy, compare_versions, extract_obligations, jaccard, segment_clauses


def _signal(status: dict[str, str | bool], cosine: float | None = None) -> dict[str, Any]:
    return {
        "state": status["state"],
        "modelId": status["modelId"],
        "detail": status["detail"],
        "cosineSimilarity": cosine,
    }


def compare_policy_hybrid(regulatory_text: str, policy_text: str) -> dict[str, Any]:
    status = legalbert.model_status()
    if not status["ready"]:
        result = compare_policy(regulatory_text, policy_text)
        result["modelSignal"] = _signal(status)
        return result
    try:
        requirements = extract_obligations(regulatory_text)
        if not requirements:
            result = compare_policy(regulatory_text, policy_text)
            result["modelSignal"] = _signal({"state": "ready", "modelId": legalbert.MODEL_ID, "detail": "No regulatory clause was long enough for model retrieval; rules used."})
            return result
        requirement = requirements[0]
        candidates = segment_clauses(policy_text)
        if not candidates:
            result = compare_policy(regulatory_text, policy_text)
            result["modelSignal"] = _signal(status)
            return result
        candidate_records = extract_obligations(policy_text)
        lexical = [jaccard(requirement["action"], record["action"]) for record in candidate_records]
        shortlist = sorted(range(len(candidates)), key=lambda index: lexical[index], reverse=True)[:64]
        scores = legalbert.similarity_matrix([requirement["action"]], [candidate_records[index]["action"] for index in shortlist])[0]
        ranked = [(0.55 * scores[position] + 0.45 * lexical[index], scores[position], index) for position, index in enumerate(shortlist)]
        _, cosine, selected_index = max(ranked)
        result = compare_policy(regulatory_text, candidates[selected_index])
        result["retrieval"] = {
            "candidateCount": len(candidates),
            "consideredCount": len(shortlist),
            "selectedIndex": selected_index,
            "selectedClause": candidates[selected_index],
            "method": "hybrid-legal-bert-lexical",
        }
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        result = compare_policy(regulatory_text, policy_text)
        result["modelSignal"] = _signal({"state": "error", "modelId": legalbert.MODEL_ID, "detail": f"Legal-BERT inference failed: {type(exc).__name__}. Rules used."})
        return result
    result["modelSignal"] = _signal({"state": "active", "modelId": legalbert.MODEL_ID, "detail": "Legal-BERT and lexical overlap selected the policy clause; the verdict still uses explicit constraints."}, cosine)
    return result


def compare_versions_hybrid(old_text: str, new_text: str) -> dict[str, Any]:
    status = legalbert.model_status()
    if not status["ready"]:
        result = compare_versions(old_text, new_text)
        result["modelSignal"] = _signal(status)
        return result
    try:
        old_clauses = segment_clauses(old_text)
        new_clauses = segment_clauses(new_text)
        scores = legalbert.similarity_matrix(old_clauses, new_clauses)
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        result = compare_versions(old_text, new_text)
        result["modelSignal"] = _signal({"state": "error", "modelId": legalbert.MODEL_ID, "detail": f"Legal-BERT inference failed: {type(exc).__name__}. Rules used."})
        return result
    result = compare_versions(old_text, new_text, semantic_scores=scores)
    result["modelSignal"] = _signal({"state": "active", "modelId": legalbert.MODEL_ID, "detail": "Legal-BERT vectors assisted clause alignment; rule checks still determine materiality."})
    return result
