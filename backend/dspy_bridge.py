"""Optional DSPy deontic candidate generator.

Candidates are never used as solver facts without deterministic validation and
explicit scenario grounding. No external model is called unless configured.
"""

from __future__ import annotations

import importlib.util
import os
from typing import Any


def suggest(clauses: list[str]) -> tuple[list[dict[str, str]], dict[str, str]]:
    model_name = os.getenv("REGULATRACE_DSPY_MODEL", "").strip()
    if not model_name:
        return [], {"name": "DSPy extraction", "state": "not-configured", "detail": "Set REGULATRACE_DSPY_MODEL to enable LM-generated review candidates; deterministic tuples drive Z3."}
    if importlib.util.find_spec("dspy") is None:
        return [], {"name": "DSPy extraction", "state": "not-configured", "detail": "A model is configured but DSPy is not installed; install requirements-research.txt."}
    try:
        import dspy

        kwargs: dict[str, Any] = {}
        if os.getenv("REGULATRACE_DSPY_API_BASE"):
            kwargs["api_base"] = os.environ["REGULATRACE_DSPY_API_BASE"]
        if os.getenv("REGULATRACE_DSPY_API_KEY"):
            kwargs["api_key"] = os.environ["REGULATRACE_DSPY_API_KEY"]
        lm = dspy.LM(model_name, **kwargs)
        signature = dspy.Signature(
            "clause -> actor, action, modality, entity, scope, exception",
            instructions="Extract a legal norm as short fields. action is ERASE, RETAIN, or OTHER; modality is O, F, P, or UNKNOWN. Do not invent entities, roles, or exceptions.",
        )
        program = dspy.Predict(signature)
        suggestions: list[dict[str, str]] = []
        with dspy.context(lm=lm):
            for clause in clauses:
                prediction = program(clause=clause)
                suggestion = {name: str(getattr(prediction, name, "")).strip() for name in ("actor", "action", "modality", "entity", "scope", "exception")}
                if suggestion["action"].upper() not in {"ERASE", "RETAIN", "OTHER"} or suggestion["modality"].upper() not in {"O", "F", "P", "UNKNOWN"}:
                    raise ValueError("DSPy output did not satisfy the deontic contract")
                suggestion["action"] = suggestion["action"].upper()
                suggestion["modality"] = suggestion["modality"].upper()
                suggestions.append(suggestion)
        return suggestions, {"name": "DSPy extraction", "state": "active", "detail": "LM generated review candidates. The audited deterministic tuples still control the proof."}
    except Exception as exc:
        return [], {"name": "DSPy extraction", "state": "error", "detail": f"Configured LM extraction failed ({type(exc).__name__}); no suggestions used in proof."}
