"""Behavioral tests for scoped contradiction proof and source exceptions."""

from copy import deepcopy
import sys
import types

import pytest
from fastapi.testclient import TestClient

from backend.contradictions import OFFICIAL_EXAMPLE, SYNTHETIC_EXAMPLE
from backend.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def no_large_model(monkeypatch):
    monkeypatch.setenv("REGULATRACE_INLEGALBERT", "off")
    monkeypatch.delenv("REGULATRACE_NEO4J_URI", raising=False)


def run(example: dict) -> dict:
    response = client.post("/api/contradictions/analyze", json=example["request"])
    assert response.status_code == 200, response.text
    return response.json()


def test_official_pair_is_satisfiable_because_of_legal_retention_exception() -> None:
    result = run(OFFICIAL_EXAMPLE)
    assert result["verdict"] == "SAT"
    assert result["proof"]["check"] == "sat"
    assert result["tuples"][0]["status"] == "EXCEPTED"
    assert result["tuples"][1]["status"] == "ACTIVE"
    assert result["proof"]["unsatCore"] == []
    assert result["graph"]["backend"] == "in-memory"
    assert result["dspySuggestions"] == []
    assert next(stage for stage in result["stages"] if stage["name"] == "DSPy extraction")["state"] == "not-configured"


def test_dpdp_clause_is_not_effective_in_october_2026() -> None:
    example = deepcopy(OFFICIAL_EXAMPLE)
    example["request"]["context"]["asOf"] = "2026-10-27"
    example["request"]["context"]["eventDate"] = "2026-10-20"
    result = run(example)
    assert result["verdict"] == "SAT"
    assert result["tuples"][0]["status"] == "INACTIVE"
    assert "2027-05-13" in result["tuples"][0]["reason"]


def test_synthetic_deadlock_has_two_source_unsat_core() -> None:
    result = run(SYNTHETIC_EXAMPLE)
    assert result["verdict"] == "UNSAT"
    assert result["proof"]["check"] == "unsat"
    assert set(result["proof"]["unsatCore"]) == {"DEMO-ERASE", "DEMO-KEEP"}
    assert len(result["proof"]["constraints"]) == 2


def test_missing_actor_grounding_is_inconclusive() -> None:
    example = deepcopy(SYNTHETIC_EXAMPLE)
    example["request"]["clauses"][1]["actorHint"] = "Payment Gateway"
    result = run(example)
    assert result["verdict"] == "INDETERMINATE"
    assert result["tuples"][1]["status"] == "UNRESOLVED"
    assert "graph path" in result["tuples"][1]["reason"]


def test_unknown_event_date_does_not_invent_retention_applicability() -> None:
    example = deepcopy(SYNTHETIC_EXAMPLE)
    example["request"]["context"]["eventDate"] = None
    result = run(example)
    assert result["verdict"] == "INDETERMINATE"
    assert all(item["status"] == "UNRESOLVED" for item in result["tuples"])


def test_examples_and_openapi_are_available() -> None:
    response = client.get("/api/contradictions/examples")
    assert response.status_code == 200
    assert {item["id"] for item in response.json()} == {"official-conditional-retention", "synthetic-unsat"}
    assert "/api/contradictions/analyze" in client.get("/api/openapi.json").json()["paths"]


def test_epistemic_may_not_does_not_create_a_prohibition() -> None:
    example = deepcopy(SYNTHETIC_EXAMPLE)
    example["request"]["clauses"][1]["text"] = "The organization may not be able to erase customer identification records after account closure."
    result = run(example)
    assert result["verdict"] == "INDETERMINATE"
    assert result["tuples"][1]["modality"] == "UNKNOWN"


def test_unresolved_legal_exception_prevents_false_deadlock() -> None:
    example = deepcopy(SYNTHETIC_EXAMPLE)
    example["request"]["clauses"][0]["text"] += " Retention may nevertheless be required for compliance with any law."
    example["request"]["clauses"][0]["text"] = example["request"]["clauses"][0]["text"].replace(" Retention may", " Unless retention is necessary for legal compliance, retention may")
    result = run(example)
    assert result["verdict"] == "INDETERMINATE"
    assert result["tuples"][0]["status"] == "UNRESOLVED"


def test_source_precision_labels_deterministic_fallback(monkeypatch) -> None:
    from backend import ragas_bridge

    monkeypatch.setattr(ragas_bridge.importlib.util, "find_spec", lambda _name: None)
    response = client.post("/api/contradictions/score-sources", json={
        "retrievedContextIds": ["DPDP-8-7", "RBI-KYC-46", "irrelevant"],
        "referenceContextIds": ["DPDP-8-7", "RBI-KYC-46"],
    })
    assert response.status_code == 200
    assert response.json()["backend"] == "deterministic"
    assert response.json()["precision"] == 0.6667


def test_configured_dspy_candidates_do_not_override_z3(monkeypatch) -> None:
    from backend import dspy_bridge

    fake = types.ModuleType("dspy")
    fake.LM = lambda *_args, **_kwargs: object()
    fake.Signature = lambda *_args, **_kwargs: object()
    fake.Predict = lambda _signature: lambda **_kwargs: types.SimpleNamespace(actor="organization", action="ERASE", modality="O", entity="records", scope="general", exception="none")

    class FakeContext:
        def __enter__(self):
            return None

        def __exit__(self, *_args):
            return False

    fake.context = lambda **_kwargs: FakeContext()
    monkeypatch.setitem(sys.modules, "dspy", fake)
    monkeypatch.setattr(dspy_bridge.importlib.util, "find_spec", lambda _name: object())
    monkeypatch.setenv("REGULATRACE_DSPY_MODEL", "local/test")
    result = run(SYNTHETIC_EXAMPLE)
    assert result["verdict"] == "UNSAT"
    assert len(result["dspySuggestions"]) == 2
    assert next(stage for stage in result["stages"] if stage["name"] == "DSPy extraction")["state"] == "active"


def test_ragas_adapter_uses_metric_when_installed(monkeypatch) -> None:
    from backend import ragas_bridge

    fake_ragas = types.ModuleType("ragas")
    fake_ragas.SingleTurnSample = lambda **kwargs: kwargs
    fake_metrics = types.ModuleType("ragas.metrics")

    class FakeMetric:
        async def single_turn_ascore(self, sample):
            return len(set(sample["retrieved_context_ids"]) & set(sample["reference_context_ids"])) / len(sample["retrieved_context_ids"])

    fake_metrics.IDBasedContextPrecision = FakeMetric
    monkeypatch.setitem(sys.modules, "ragas", fake_ragas)
    monkeypatch.setitem(sys.modules, "ragas.metrics", fake_metrics)
    monkeypatch.setattr(ragas_bridge.importlib.util, "find_spec", lambda _name: object())
    response = client.post("/api/contradictions/score-sources", json={"retrievedContextIds": ["a", "b"], "referenceContextIds": ["b"]})
    assert response.status_code == 200
    assert response.json()["backend"] == "ragas"
    assert response.json()["precision"] == 0.5
