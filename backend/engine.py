"""Python port of dist/js/engine.js.

This module deliberately preserves the deterministic JavaScript baseline's
semantics. It is not a legal decision-maker and does not use a learned model.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

ENGINE_VERSION = "0.4.0-research"

MODALITY_PATTERNS = [
    ("PROHIBITION", re.compile(r"\b(must\s+not|shall\s+not|may\s+not|is\s+prohibited\s+from|are\s+prohibited\s+from|is\s+forbidden\s+to)\b", re.I), 0.98),
    ("OBLIGATION", re.compile(r"\b(must|shall|is\s+required\s+to|are\s+required\s+to|has\s+to|have\s+to|is\s+obliged\s+to)\b", re.I), 0.96),
    ("RECOMMENDATION", re.compile(r"\b(should|ought\s+to|is\s+recommended\s+to|are\s+encouraged\s+to)\b", re.I), 0.88),
    ("PERMISSION", re.compile(r"\b(may|is\s+permitted\s+to|are\s+permitted\s+to|is\s+allowed\s+to)\b", re.I), 0.90),
]

DEADLINE_PATTERNS = [
    re.compile(r"\b(?:no|not)\s+later\s+than\s+\d+\s+(?:hours?|days?|weeks?|months?|years?)(?:\s+after\s+[^,.;]+)?", re.I),
    re.compile(r"\bwithin\s+\d+\s+(?:hours?|days?|weeks?|months?|years?)(?:\s+(?:of|after|from)\s+[^,.;]+)?", re.I),
    re.compile(r"\bat\s+least\s+(?:once\s+)?every\s+\d+\s+(?:days?|weeks?|months?|years?)", re.I),
    re.compile(r"\bevery\s+\d+\s+(?:days?|weeks?|months?|years?)", re.I),
    re.compile(r"\bwithout\s+undue\s+delay", re.I),
    re.compile(r"\b(?:daily|weekly|monthly|quarterly|annually|immediately|promptly)\b", re.I),
    re.compile(r"\bas\s+soon\s+as\s+(?:practicable|possible)", re.I),
    re.compile(r"\bbefore\s+[^,.;]+", re.I),
]

CONDITION_RE = re.compile(r"\b(?:if|when|where|whenever|in\s+the\s+event\s+that|provided\s+that)\s+([^.;]+)", re.I)
EXCEPTION_RE = re.compile(r"\b(?:unless|except(?:\s+where|\s+when|\s+for)?|save\s+where|other\s+than)\s+([^.;]+)", re.I)
CROSS_REF_RE = re.compile(r"\b(?:Article|Section|Clause|Paragraph|Annex)\s+[A-Za-z0-9().-]+", re.I)
SEVERITY_TERMS = re.compile(r"\b(?:breach|penalty|fine|sanction|suspend|revoke|incident|risk|harm|rights|security|safety)\b", re.I)
EPISTEMIC_MAY_NOT = re.compile(r"\bmay\s+not\s+(?:be|have\s+been)\s+(?:available|complete|known|accurate|possible|sufficient|reliable|representative|applicable)\b", re.I)
STOPWORDS = set("a an the and or but if then than of to for from by with without in on at as is are was were be been being this that these those it its their they them shall should must may not no later where when which who whom into any all each every such under over".split())


def clean(text: str = "") -> str:
    return re.sub(r"^[-–—•\d.)\s]+", "", re.sub(r"\s+", " ", text)).strip()


def _base36(value: int) -> str:
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if value == 0:
        return "0"
    output = ""
    while value:
        value, remainder = divmod(value, 36)
        output = alphabet[remainder] + output
    return output


def stable_hash(value: str) -> str:
    result = 2166136261
    # JavaScript charCodeAt iterates UTF-16 code units.
    encoded = value.encode("utf-16-le")
    for unit_index in range(0, len(encoded), 2):
        code_unit = encoded[unit_index] | (encoded[unit_index + 1] << 8)
        result ^= code_unit
        result = (result * 16777619) & 0xFFFFFFFF
    return _base36(result).rjust(7, "0")


def segment_clauses(text: str = "") -> list[str]:
    normalized = text.replace("\r", "")
    normalized = re.sub(r"\n{2,}", "\n", normalized)
    normalized = re.sub(r"([.;!?])\s+(?=[A-Z(\[])", r"\1\n", normalized)
    normalized = re.sub(r";\s+(?=(?:and|or|the|a|an|each|every|where|when|if|unless|provided)\b)", ";\n", normalized, flags=re.I)
    clauses: list[str] = []
    for raw_part in re.split(r"\n+", normalized):
        part = clean(raw_part)
        if len(part) < 12:
            continue
        numbered = [clean(piece) for piece in re.split(r"(?=\s*\([a-z0-9ivx]+\)\s+)", part, flags=re.I)]
        numbered = [piece for piece in numbered if len(piece) >= 12]
        clauses.extend(numbered if len(numbered) > 1 else [part])
    return clauses


def classify_modality(clause: str = "") -> dict[str, Any]:
    epistemic = EPISTEMIC_MAY_NOT.search(clause)
    if epistemic:
        cue_match = re.search(r"\bmay\s+not\b", clause, re.I)
        return {"label": "INFORMATION", "cue": "may not (epistemic)", "index": cue_match.start() if cue_match else -1, "confidence": 0.84}
    for label, pattern, weight in MODALITY_PATTERNS:
        match = pattern.search(clause)
        if match:
            return {"label": label, "cue": match.group(0), "index": match.start(), "confidence": weight}
    return {"label": "INFORMATION", "cue": "descriptive", "index": -1, "confidence": 0.72}


def first_match(text: str, patterns: list[re.Pattern[str]]) -> str | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None


def strip_trailing_logic(text: str) -> str:
    leading = re.split(r"\b(?:if|when|where|unless|except|provided\s+that)\b", text, maxsplit=1, flags=re.I)[0]
    return re.sub(r"[,:;.]$", "", clean(leading))


def token_set(text: str = "") -> set[str]:
    return {token for token in re.findall(r"[a-z][a-z-]{2,}", text.lower()) if token not in STOPWORDS}


def jaccard(left_text: str, right_text: str) -> float:
    left = token_set(left_text)
    right = token_set(right_text)
    if not left or not right:
        return 0
    return len(left & right) / len(left | right)


def derive_actor(clause: str, modality: dict[str, Any]) -> str:
    if modality["index"] < 1:
        return "Unresolved actor"
    actor = clean(clause[: modality["index"]])
    actor = re.sub(r"^(?:if|when|where|whenever)\s+.+?,\s*", "", actor, flags=re.I)
    if "," in actor:
        actor = actor.rsplit(",", 1)[1].strip()
    return "Unresolved actor" if len(actor) > 80 or len(actor) < 2 else actor


def derive_action(clause: str, modality: dict[str, Any]) -> str:
    if modality["index"] < 0:
        return strip_trailing_logic(clause)
    after = clause[modality["index"] + len(modality["cue"]) :]
    return strip_trailing_logic(after) or "Unresolved action"


def confidence_for(record: dict[str, Any]) -> float:
    score = 0.54 if record["modality"] == "INFORMATION" else record["modalityConfidence"]
    score += 0.03 if record["actor"] != "Unresolved actor" else -0.14
    if record["action"] != "Unresolved action" and len(record["action"]) > 5:
        score += 0.02
    if len(record["evidence"]) > 220:
        score -= 0.04
    if record["crossReferences"]:
        score -= 0.02
    return max(0.35, min(0.99, score))


def extract_obligations(text: str = "", meta: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    metadata = meta or {}
    records: list[dict[str, Any]] = []
    for index, clause in enumerate(segment_clauses(text)):
        modality = classify_modality(clause)
        condition_match = CONDITION_RE.search(clause)
        exception_match = EXCEPTION_RE.search(clause)
        condition = condition_match.group(1).strip() if condition_match else None
        exception = exception_match.group(1).strip() if exception_match else None
        deadline = first_match(clause, DEADLINE_PATTERNS)
        cross_references = [match.group(0) for match in CROSS_REF_RE.finditer(clause)]
        actor = derive_actor(clause, modality)
        action = derive_action(clause, modality)
        authority = metadata.get("authority") or "Demo corpus"
        section = metadata.get("section") or f"Clause {index + 1}"
        record: dict[str, Any] = {
            "id": f"RT-{stable_hash(f'{authority}|{section}|{clause}')}",
            "sourceId": metadata.get("sourceId") or "demo://regulation",
            "sourceVersion": metadata.get("version") or "v1",
            "authority": authority,
            "jurisdiction": metadata.get("jurisdiction") or "EU",
            "section": section,
            "modality": modality["label"],
            "modalityCue": modality["cue"],
            "modalityConfidence": modality["confidence"],
            "actor": actor,
            "action": action,
            "deadline": deadline,
            "condition": condition,
            "exception": exception,
            "crossReferences": cross_references,
            "evidence": clause,
            "reviewState": "UNREVIEWED",
            "severity": "HIGH" if SEVERITY_TERMS.search(clause) else ("MEDIUM" if deadline else "STANDARD"),
            "unresolved": (["actor"] if actor == "Unresolved actor" else []) + (["cross-reference-context"] if cross_references else []),
        }
        record["confidence"] = confidence_for(record)
        records.append(record)
    return records


def analyze_document(text: str = "", meta: dict[str, Any] | None = None) -> dict[str, Any]:
    metadata = meta or {}
    records = extract_obligations(text, metadata)
    normative = [record for record in records if record["modality"] != "INFORMATION"]
    counts: dict[str, int] = {}
    for record in records:
        counts[record["modality"]] = counts.get(record["modality"], 0) + 1
    avg_confidence = sum(record["confidence"] for record in normative) / len(normative) if normative else 0
    citation_integrity = sum(1 for record in records if record["sourceId"] and record["evidence"]) / len(records) if records else 0
    timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return {
        "engineVersion": ENGINE_VERSION,
        "analyzedAt": timestamp,
        "source": metadata,
        "records": records,
        "normative": normative,
        "summary": {
            "clauseCount": len(records),
            "obligationCount": sum(1 for record in normative if record["modality"] == "OBLIGATION"),
            "unresolvedCount": sum(1 for record in records if record["unresolved"]),
            "avgConfidence": avg_confidence,
            "citationIntegrity": citation_integrity,
            "modalityCounts": counts,
        },
    }


def deadline_number(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"(\d+)\s*(hour|day|week|month|year)", value, re.I)
    if not match:
        return None
    multipliers = {"hour": 1, "day": 24, "week": 168, "month": 730, "year": 8760}
    return int(match.group(1)) * multipliers[match.group(2).lower()]


def compare_policy(requirement_text: str = "", policy_text: str = "") -> dict[str, Any]:
    requirement_records = extract_obligations(requirement_text)
    policy_records = extract_obligations(policy_text)
    requirement = requirement_records[0] if requirement_records else None
    policy = policy_records[0] if policy_records else None
    lexical = jaccard(requirement_text, policy_text)
    req_deadline = deadline_number(requirement.get("deadline") if requirement else None)
    policy_deadline = deadline_number(policy.get("deadline") if policy else None)
    dimensions = [
        {
            "id": "actor",
            "label": "Actor",
            "score": jaccard(requirement["actor"], policy["actor"]) if requirement and policy else 0,
            "detail": f"{requirement['actor'] if requirement else 'Unresolved'} ↔ {policy['actor'] if policy else 'Unresolved'}",
        },
        {
            "id": "action",
            "label": "Action & object",
            "score": max(lexical, jaccard(requirement["action"], policy["action"])) if requirement and policy else 0,
            "detail": policy["action"] if policy else "No policy action located",
        },
        {
            "id": "polarity",
            "label": "Polarity",
            "score": 1 if requirement and policy and requirement["modality"] == policy["modality"] else 0.3,
            "detail": f"{requirement['modality'] if requirement else '?'} ↔ {policy['modality'] if policy else '?'}",
        },
        {
            "id": "timing",
            "label": "Timing",
            "score": (1 if policy_deadline <= req_deadline else max(0, req_deadline / policy_deadline)) if req_deadline and policy_deadline else (0.2 if req_deadline else 0.8),
            "detail": f"{policy['deadline'] if policy and policy['deadline'] else 'No policy deadline'} against {requirement['deadline']}" if req_deadline else "No numeric regulatory deadline detected",
        },
        {
            "id": "exception",
            "label": "Exception scope",
            "score": (jaccard(requirement["exception"], policy["exception"]) if policy and policy["exception"] else 0.25) if requirement and requirement["exception"] else 0.9,
            "detail": (policy["exception"] if policy and policy["exception"] else "Regulatory exception not represented") if requirement and requirement["exception"] else "No explicit exception in selected requirement",
        },
        {
            "id": "evidence",
            "label": "Evidence sufficiency",
            "score": 0.92 if len(policy_text.strip()) > 40 else 0.45,
            "detail": "Policy text is substantial enough for review" if len(policy_text.strip()) > 40 else "Policy evidence is too short",
        },
    ]
    weights = {"actor": 0.12, "action": 0.24, "polarity": 0.18, "timing": 0.24, "exception": 0.12, "evidence": 0.10}
    score = sum(dimension["score"] * weights[dimension["id"]] for dimension in dimensions)
    critical_failure = any(
        (dimension["id"] == "polarity" and dimension["score"] < 0.55)
        or (dimension["id"] == "timing" and req_deadline and policy_deadline and policy_deadline > req_deadline)
        or (dimension["id"] == "timing" and req_deadline and not policy_deadline)
        for dimension in dimensions
    )
    outcome = "POTENTIAL_MISMATCH" if critical_failure or score < 0.62 else ("LIKELY_ALIGNED" if score >= 0.82 else "REVIEW_REQUIRED")
    return {"requirement": requirement, "policy": policy, "dimensions": dimensions, "score": score, "outcome": outcome, "lexicalSimilarity": lexical}


def change_severity(before: str, after: str) -> str:
    combined = f"{before} {after}"
    before_modal = classify_modality(before)["label"]
    after_modal = classify_modality(after)["label"]
    before_period = time_quantity(before)
    after_period = time_quantity(after)
    before_deadline = deadline_number(first_match(before, DEADLINE_PATTERNS)) or (before_period[1] if before_period else None)
    after_deadline = deadline_number(first_match(after, DEADLINE_PATTERNS)) or (after_period[1] if after_period else None)
    if before_modal != after_modal or (before_deadline and after_deadline and after_deadline < before_deadline) or SEVERITY_TERMS.search(combined):
        return "CRITICAL"
    return "MATERIAL"


TIME_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "twenty-four": 24,
}
TIME_QUANTITY_RE = re.compile(
    r"(?<![\w-])(\d+|twenty-four|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+"
    r"(hours?|days?|weeks?|months?|years?)\b", re.I,
)
TIME_HOURS = {"hour": 1, "day": 24, "week": 168, "month": 730, "year": 8760}
RETENTION_RE = re.compile(r"\b(?:retain|retention|preserve|keep|store|archive)\b", re.I)


def time_quantity(text: str) -> tuple[str, int] | None:
    match = TIME_QUANTITY_RE.search(text)
    if not match:
        return None
    amount = int(match.group(1)) if match.group(1).isdigit() else TIME_WORDS[match.group(1).lower()]
    unit = match.group(2).lower().rstrip("s")
    return match.group(0), amount * TIME_HOURS[unit]


def explain_change(change_type: str, before: str | None, after: str | None) -> dict[str, str]:
    """Explain observable edits; infer intent only when a concrete cue supports it."""
    if change_type == "ADDED":
        return {
            "observed": "A clause appears in the new version without a close match in the old version.",
            "possibleRationale": "The reason for adding this clause cannot be established from the two versions alone.",
            "operationalImpact": "Assign an owner and check whether policies, controls, deadlines, and evidence need updating.",
            "status": "UNDETERMINED",
        }
    if change_type == "REMOVED":
        return {
            "observed": "A clause in the old version has no close match in the new version.",
            "possibleRationale": "The reason for removal is unknown; the requirement may have moved elsewhere.",
            "operationalImpact": "Check the full new instrument before retiring any policy or control.",
            "status": "UNDETERMINED",
        }

    previous = before or ""
    current = after or ""
    old_time = time_quantity(previous)
    new_time = time_quantity(current)
    if old_time and new_time and old_time[1] != new_time[1]:
        retention = bool(RETENTION_RE.search(previous) and RETENTION_RE.search(current))
        direction = "extended" if new_time[1] > old_time[1] else "shortened"
        if retention:
            rationale = "This may aim to preserve records for longer review or investigation." if direction == "extended" else "This may reduce the required storage period."
            impact = "Review retention schedules, deletion rules, and evidence storage."
            observed = f"The retention period changed from {old_time[0]} to {new_time[0]} ({direction})."
        else:
            rationale = "This may aim to accelerate reporting or action." if direction == "shortened" else "This may allow more time to complete the required action."
            impact = "Review deadlines, escalation paths, owners, and monitoring controls."
            observed = f"The stated time window changed from {old_time[0]} to {new_time[0]} ({direction})."
        return {"observed": observed, "possibleRationale": rationale, "operationalImpact": impact, "status": "INFERRED_FROM_TEXT"}

    old_modal = classify_modality(previous)["label"]
    new_modal = classify_modality(current)["label"]
    if old_modal != new_modal:
        return {
            "observed": f"The clause changed from {old_modal.lower()} to {new_modal.lower()} language.",
            "possibleRationale": "This may change the level of discretion or the strength of the duty.",
            "operationalImpact": "Review policy wording, decision rights, and required controls against the new modality.",
            "status": "INFERRED_FROM_TEXT",
        }

    old_exception = bool(EXCEPTION_RE.search(previous))
    new_exception = bool(EXCEPTION_RE.search(current))
    if old_exception != new_exception:
        return {
            "observed": "An explicit exception was added." if new_exception else "An explicit exception was removed.",
            "possibleRationale": "This may change when the duty applies.",
            "operationalImpact": "Review exception approvals and the evidence required to apply them.",
            "status": "INFERRED_FROM_TEXT",
        }

    return {
        "observed": "The clause wording changed, but no supported reason was identified from the text alone.",
        "possibleRationale": "Check official recitals, consultation records, or explanatory notes for the regulator's stated reason.",
        "operationalImpact": "Ask a reviewer to compare the old and new duties before changing controls.",
        "status": "UNDETERMINED",
    }


def compare_versions(old_text: str = "", new_text: str = "", semantic_scores: list[list[float]] | None = None) -> dict[str, Any]:
    old_clauses = segment_clauses(old_text)
    new_clauses = segment_clauses(new_text)
    matched_old: set[int] = set()
    changes: list[dict[str, Any]] = []
    for current_index, current in enumerate(new_clauses):
        best_index = -1
        best_score = 0.0
        for index, previous in enumerate(old_clauses):
            if index in matched_old:
                continue
            similarity = jaccard(previous, current)
            if similarity > best_score:
                best_score = similarity
                best_index = index
        alignment_method = "lexical" if best_index >= 0 and best_score >= 0.38 else "none"
        if alignment_method == "none" and semantic_scores is not None:
            current_modality = classify_modality(current)
            current_actor = derive_actor(current, current_modality)
            semantic_candidates = [
                (semantic_scores[index][current_index], jaccard(previous, current), index)
                for index, previous in enumerate(old_clauses)
                if index not in matched_old
                and classify_modality(previous)["label"] == current_modality["label"]
                and jaccard(derive_actor(previous, classify_modality(previous)), current_actor) >= 0.5
            ]
            if semantic_candidates:
                semantic_candidates.sort(reverse=True)
                semantic, lexical, candidate_index = semantic_candidates[0]
                margin = semantic - semantic_candidates[1][0] if len(semantic_candidates) > 1 else 1.0
                if semantic >= 0.87 and lexical >= 0.2 and margin >= 0.025:
                    best_index, best_score, alignment_method = candidate_index, lexical, "legal-bert"
        if best_index >= 0 and alignment_method != "none":
            matched_old.add(best_index)
            previous = old_clauses[best_index]
            if best_score < 0.965 or clean(previous).lower() != clean(current).lower():
                changes.append({"id": f"CH-{stable_hash(previous + current)}", "type": "MODIFIED", "before": previous, "after": current, "similarity": best_score, "severity": change_severity(previous, current), "explanation": explain_change("MODIFIED", previous, current), "alignmentMethod": alignment_method, "semanticSimilarity": semantic_scores[best_index][current_index] if semantic_scores is not None else None})
        else:
            changes.append({"id": f"CH-{stable_hash(current)}", "type": "ADDED", "before": None, "after": current, "similarity": 0, "severity": "CRITICAL" if SEVERITY_TERMS.search(current) else "MATERIAL", "explanation": explain_change("ADDED", None, current), "alignmentMethod": "none", "semanticSimilarity": None})
    for index, previous in enumerate(old_clauses):
        if index not in matched_old:
            changes.append({"id": f"CH-{stable_hash(previous)}", "type": "REMOVED", "before": previous, "after": None, "similarity": 0, "severity": "CRITICAL", "explanation": explain_change("REMOVED", previous, None), "alignmentMethod": "none", "semanticSimilarity": None})
    counts: dict[str, int] = {}
    for change in changes:
        counts[change["type"]] = counts.get(change["type"], 0) + 1
    return {
        "changes": changes,
        "counts": counts,
        "affectedObligations": sum(1 for change in changes if change["type"] != "ADDED"),
        "criticalCount": sum(1 for change in changes if change["severity"] == "CRITICAL"),
        "materialityScore": min(100, round(sum(28 if change["severity"] == "CRITICAL" else 14 for change in changes))),
    }

