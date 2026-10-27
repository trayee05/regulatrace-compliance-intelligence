"""Evidence-first, scoped deontic contradiction checks with Z3.

An UNSAT result proves that the *modeled* constraints cannot both hold for the
selected actor, record and date. It does not determine statutory priority or
replace a lawyer's interpretation of the original sources.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, timedelta
from typing import Any

from z3 import Bool, Not, Solver, sat, unsat

from backend import inlegalbert
from backend.dspy_bridge import suggest as dspy_suggest
from backend.engine import classify_modality, derive_actor, time_quantity
from backend.graph_bridge import publish_graph
from backend.schemas import ContradictionClause, ContradictionContext, ContradictionRequest

ERASE_RE = re.compile(r"\b(?:erase|delete|remove|purge|destroy|erasure|deletion)\b", re.I)
RETAIN_RE = re.compile(r"\b(?:retain|retention|preserve|keep|maintain|store)\b", re.I)
NEGATIVE_RE = re.compile(r"\b(?:must\s+not|shall\s+not|may\s+not|prohibited\s+from)\b", re.I)
OBLIGATION_RE = re.compile(r"\b(?:must|shall|required\s+to|obliged\s+to)\b", re.I)
PERMISSION_RE = re.compile(r"\b(?:may|permitted\s+to|allowed\s+to)\b", re.I)
LEGAL_EXCEPTION_RE = re.compile(r"\bunless\b[^.;]{0,150}\b(?:retention|retain|law|legal|compliance)\b", re.I)
EPISTEMIC_ABILITY_RE = re.compile(r"\bmay\s+not\s+be\s+(?:able|possible)\s+to\b", re.I)
ENTITY_PATTERNS = [
    ("customer identification records", re.compile(r"\b(?:customer|client)\s+(?:identification|identity|KYC)\s+records?\b", re.I)),
    ("transaction records", re.compile(r"\btransaction\s+records?\b", re.I)),
    ("customer activity records", re.compile(r"\b(?:customer|client)\s+activity\s+records?\b", re.I)),
    ("personal data", re.compile(r"\b(?:personal\s+data|user\s+PII|personally\s+identifiable\s+information)\b", re.I)),
    ("records", re.compile(r"\brecords?\b", re.I)),
]


def normalize(value: str) -> str:
    value = re.sub(r"\s+", " ", value.strip().lower())
    value = re.sub(r"^(?:the|a|an)\s+", "", value)
    return {"regulated entities": "regulated entity", "data fiduciaries": "data fiduciary", "organizations": "organization"}.get(value, value)


def _entity(text: str) -> str:
    for name, pattern in ENTITY_PATTERNS:
        if pattern.search(text):
            return name
    return "unresolved entity"


def extract_norm(clause: ContradictionClause) -> dict[str, Any]:
    text = clause.text.strip()
    modality = classify_modality(text)
    actor = normalize(clause.actor_hint or derive_actor(text, modality))
    entity = normalize(clause.entity_hint or _entity(text))
    if ERASE_RE.search(text):
        action = "ERASE"
    elif RETAIN_RE.search(text):
        action = "RETAIN"
    else:
        action = "OTHER"
    if modality["cue"] == "may not (epistemic)" or EPISTEMIC_ABILITY_RE.search(text):
        deontic = "UNKNOWN"
    elif NEGATIVE_RE.search(text):
        deontic = "F"
    elif OBLIGATION_RE.search(text):
        deontic = "O"
    elif PERMISSION_RE.search(text):
        deontic = "P"
    else:
        deontic = "UNKNOWN"
    period = time_quantity(text)
    duration_days = round(period[1] / 24) if period and re.search(r"\b(?:for|at\s+least)\b", text[: text.find(period[0])], re.I) else None
    if re.search(r"\b(?:account\s+clos(?:ure|ed)|business\s+relationship\s+(?:is\s+)?end(?:ed|s)?)\b", text, re.I):
        scope = "after relationship end or account closure"
    elif re.search(r"\b(?:purpose\s+(?:is\s+)?no\s+longer\s+served|purpose\s+ended)\b", text, re.I):
        scope = "when specified purpose ends"
    else:
        scope = "general"
    return {
        "id": clause.id,
        "sourceId": clause.citation,
        "sourceUrl": clause.source_url,
        "actor": actor,
        "action": action,
        "modality": deontic,
        "entity": entity,
        "scope": scope,
        "durationDays": duration_days,
        "exception": "legal retention required" if LEGAL_EXCEPTION_RE.search(text) else None,
        "evidence": text,
        "extractionMethod": "pattern + Pydantic validation",
        "status": "UNRESOLVED",
        "reason": "Applicability not checked yet.",
    }


def _reachability(facts: list[dict[str, str]], specific: str, general: str) -> bool:
    specific, general = normalize(specific), normalize(general)
    if specific == general:
        return True
    adjacency: dict[str, set[str]] = {}
    for fact in facts:
        subject, obj = normalize(fact["subject"]), normalize(fact["object"])
        adjacency.setdefault(subject, set()).add(obj)
        if fact["relation"] == "SAME_AS":
            adjacency.setdefault(obj, set()).add(subject)
    stack = [specific]
    seen: set[str] = set()
    while stack:
        current = stack.pop()
        if current == general:
            return True
        if current in seen:
            continue
        seen.add(current)
        stack.extend(adjacency.get(current, set()) - seen)
    return False


def _base_status(norm: dict[str, Any], clause: ContradictionClause, context: ContradictionContext, facts: list[dict[str, str]]) -> tuple[str, str]:
    if clause.effective_from and context.as_of < clause.effective_from:
        return "INACTIVE", f"The source is not effective until {clause.effective_from.isoformat()}."
    if not _reachability(facts, context.target_actor, norm["actor"]):
        return "UNRESOLVED", "The target actor has no supplied graph path to this legal role."
    if not _reachability(facts, context.target_entity, norm["entity"]):
        return "UNRESOLVED", "The target record has no supplied graph path to this entity scope."
    if norm["action"] == "OTHER" or norm["modality"] == "UNKNOWN":
        return "UNRESOLVED", "The clause cannot be compiled into a supported erase/retain constraint."
    if norm["scope"] == "when specified purpose ends" and not context.purpose_ended:
        return "INACTIVE", "The selected scenario says the specified purpose has not ended."
    if norm["scope"] == "after relationship end or account closure":
        if context.event_date is None:
            return "UNRESOLVED", "An account-closure or relationship-end date is needed."
        if context.as_of < context.event_date:
            return "INACTIVE", "The selected date precedes the account closure or relationship end."
    if norm["durationDays"] is not None:
        if context.event_date is None:
            return "UNRESOLVED", "A reference event date is needed to test the retention period."
        if context.as_of >= context.event_date + timedelta(days=norm["durationDays"]):
            return "INACTIVE", "The modeled retention period has elapsed."
    return "ACTIVE", "Actor, record scope, timing, and source effective date match the scenario."


def _graph(clauses: list[ContradictionClause], norms: list[dict[str, Any]], context: ContradictionContext, facts: list[dict[str, str]]) -> dict[str, Any]:
    nodes: dict[str, dict[str, str]] = {}
    edges: list[dict[str, str]] = []

    def add_node(kind: str, value: str) -> str:
        node_id = f"{kind}:{normalize(value)}"
        nodes[node_id] = {"id": node_id, "label": value, "type": kind}
        return node_id

    target_actor = add_node("actor", context.target_actor)
    target_entity = add_node("entity", context.target_entity)
    for clause, norm in zip(clauses, norms):
        source = add_node("source", clause.citation)
        duty = add_node("norm", clause.id)
        actor = add_node("actor", norm["actor"])
        entity = add_node("entity", norm["entity"])
        edges.extend([
            {"source": source, "target": duty, "label": "ASSERTS"},
            {"source": duty, "target": actor, "label": "BINDS"},
            {"source": duty, "target": entity, "label": "ABOUT"},
        ])
    for fact in facts:
        kind = "entity" if any(token in normalize(fact["subject"] + " " + fact["object"]) for token in ("record", "data", "pii")) else "actor"
        start = add_node(kind, fact["subject"])
        end = add_node(kind, fact["object"])
        edges.append({"source": start, "target": end, "label": fact["relation"]})
    return {"nodes": list(nodes.values()), "edges": edges, "backend": "in-memory", "detail": "Explicit facts held in the request; Neo4j sync is optional."}


def analyze_contradiction(request: ContradictionRequest) -> dict[str, Any]:
    clauses, context = request.clauses, request.context
    facts = [fact.model_dump() for fact in context.facts]
    norms = [extract_norm(clause) for clause in clauses]
    assumptions = [
        "Only the selected actor, record and as-of date are modeled.",
        "IS_A and SAME_AS links are user-supplied facts, not inferred legal equivalence.",
        "A retention obligation is modeled as no erasure during its stated period.",
        "Year-length duration is approximated as 365 days; verify statutory counting rules.",
    ]
    for norm, clause in zip(norms, clauses):
        norm["status"], norm["reason"] = _base_status(norm, clause, context, facts)

    active_retention = any(norm["status"] == "ACTIVE" and norm["modality"] == "O" and norm["action"] == "RETAIN" for norm in norms)
    for norm in norms:
        if norm["status"] == "ACTIVE" and norm["exception"] and norm["action"] == "ERASE" and active_retention:
            norm["status"] = "EXCEPTED"
            norm["reason"] = "A grounded, currently applicable retention duty triggers the clause's explicit legal-retention exception."
        elif norm["status"] == "ACTIVE" and norm["exception"] and norm["action"] == "ERASE":
            norm["status"] = "UNRESOLVED"
            norm["reason"] = "The legal-retention exception cannot be resolved from the supplied clauses and facts."

    decision = Bool("erase_selected_record_now")
    solver = Solver()
    solver.set(timeout=2500)
    constraints: list[str] = []
    tracked: dict[str, str] = {}
    for norm in norms:
        if norm["status"] != "ACTIVE":
            continue
        formula = None
        if norm["action"] == "ERASE" and norm["modality"] == "O":
            formula = decision
            expression = f"O(ERASE({normalize(context.target_entity)}))"
        elif (norm["action"] == "ERASE" and norm["modality"] == "F") or (norm["action"] == "RETAIN" and norm["modality"] == "O"):
            formula = Not(decision)
            expression = f"F(ERASE({normalize(context.target_entity)}))"
        else:
            continue
        track_id = f"rule_{len(tracked)}"
        solver.assert_and_track(formula, Bool(track_id))
        tracked[track_id] = norm["id"]
        constraints.append(f"{norm['id']}: {expression}")

    check = solver.check()
    core = [tracked[str(item)] for item in solver.unsat_core()] if check == unsat else []
    unresolved = any(norm["status"] == "UNRESOLVED" for norm in norms)
    if check == unsat:
        verdict = "UNSAT"
        summary = "A contradiction is proved for the selected actor, record, date, and supplied graph facts. The highlighted rules cannot both be obeyed."
        witness = None
    elif check == sat and unresolved:
        verdict = "INDETERMINATE"
        summary = "The active constraints are satisfiable, but at least one clause could not be grounded or compiled. No legal compatibility conclusion follows."
        witness = None
    elif check == sat:
        verdict = "SAT"
        value = solver.model().eval(decision, model_completion=True)
        witness = f"A satisfying assignment exists: erase_selected_record_now = {str(value).lower()}."
        summary = "No contradiction is proved in the modeled scenario. Check effective dates, scope, and exceptions before treating this as a legal conclusion."
    else:
        verdict = "INDETERMINATE"
        witness = None
        summary = "Z3 did not return a conclusive result within the configured limit."

    graph = _graph(clauses, norms, context, facts)
    case_id = hashlib.sha256(("|".join(clause.text for clause in clauses) + context.as_of.isoformat()).encode()).hexdigest()[:16]
    graph.update(publish_graph(case_id, graph["nodes"], graph["edges"]))

    neural_similarity = None
    model_state = inlegalbert.status()
    if model_state["ready"] and len(norms) >= 2:
        try:
            neural_similarity = inlegalbert.cosine(norms[0]["entity"], norms[1]["entity"])
            neural_stage = {"name": "InLegalBERT", "state": "active", "detail": "Indian-law encoder supplied an advisory entity cosine; graph facts control identity."}
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            neural_stage = {"name": "InLegalBERT", "state": "error", "detail": f"Local inference failed ({type(exc).__name__}); no neural grounding used."}
    else:
        neural_stage = {"name": "InLegalBERT", "state": "not-configured", "detail": str(model_state["detail"])}

    dspy_suggestions, dspy_stage = dspy_suggest([clause.text for clause in clauses])
    stages = [
        {"name": "Deontic extraction", "state": "rules", "detail": "Pattern candidates validated into typed actor/action/modality/entity/scope tuples."},
        neural_stage,
        dspy_stage,
        {"name": "Knowledge graph", "state": "active" if graph["backend"] == "neo4j" else "rules", "detail": graph["detail"]},
        {"name": "Z3 theorem prover", "state": "active", "detail": "Tracked constraints yield SAT/UNSAT and a source-linked unsat core."},
        {"name": "Ragas evaluation", "state": "not-configured", "detail": "No expert reference IDs accompany this proof. Use /api/contradictions/score-sources to evaluate source precision against labels; Ragas is optional."},
    ]
    return {
        "verdict": verdict,
        "summary": summary,
        "tuples": norms,
        "proof": {"solver": "Z3", "check": str(check), "constraints": constraints, "unsatCore": core, "witness": witness},
        "graph": graph,
        "stages": stages,
        "assumptions": assumptions,
        "neuralSimilarity": neural_similarity,
        "dspySuggestions": dspy_suggestions,
    }


OFFICIAL_EXAMPLE = {
    "id": "official-conditional-retention",
    "title": "DPDP + RBI KYC · apparent conflict resolved",
    "subtitle": "An official-source scenario with an explicit retention exception and staged commencement.",
    "request": {
        "clauses": [
            {
                "id": "DPDP-8-7",
                "text": "A Data Fiduciary shall erase personal data when the specified purpose is no longer served, unless retention is necessary for compliance with any law for the time being in force.",
                "authority": "Parliament of India",
                "citation": "DPDP Act 2023, section 8(7) (paraphrase)",
                "sourceUrl": "https://www.indiacode.nic.in/bitstream/123456789/22037/2/a2023-22.pdf",
                "effectiveFrom": "2027-05-13",
            },
            {
                "id": "RBI-KYC-46",
                "text": "Regulated entities shall preserve customer identification records for at least five years after the business relationship is ended.",
                "authority": "Reserve Bank of India",
                "citation": "RBI KYC Master Direction, paragraph 46 (paraphrase)",
                "sourceUrl": "https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=11566",
            },
        ],
        "context": {
            "asOf": "2027-06-01",
            "eventDate": "2027-05-20",
            "targetActor": "Example Bank",
            "targetEntity": "customer identification records",
            "purposeEnded": True,
            "facts": [
                {"subject": "Example Bank", "relation": "IS_A", "object": "Data Fiduciary"},
                {"subject": "Example Bank", "relation": "IS_A", "object": "Regulated Entity"},
                {"subject": "customer identification records", "relation": "IS_A", "object": "personal data"},
            ],
        },
    },
}

SYNTHETIC_EXAMPLE = {
    "id": "synthetic-unsat",
    "title": "Synthetic deadlock · provable UNSAT",
    "subtitle": "A teaching example with the same actor, record, time, and no exception. These are not real laws.",
    "request": {
        "clauses": [
            {"id": "DEMO-ERASE", "text": "The organization must erase customer identification records immediately after account closure.", "authority": "Synthetic teaching rule", "citation": "Demo Rule A"},
            {"id": "DEMO-KEEP", "text": "The organization must not erase customer identification records for five years after account closure.", "authority": "Synthetic teaching rule", "citation": "Demo Rule B"},
        ],
        "context": {"asOf": "2026-10-27", "eventDate": "2026-10-20", "targetActor": "organization", "targetEntity": "customer identification records", "purposeEnded": True, "facts": []},
    },
}

EXAMPLES = [OFFICIAL_EXAMPLE, SYNTHETIC_EXAMPLE]
