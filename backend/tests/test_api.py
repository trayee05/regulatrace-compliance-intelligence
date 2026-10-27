import pytest
from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)

GDPR = (
    "In the case of a personal data breach, the controller shall without undue delay "
    "and, where feasible, not later than 72 hours after having become aware of it, "
    "notify the personal data breach to the supervisory authority, unless the breach "
    "is unlikely to result in a risk to the rights and freedoms of natural persons."
)


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setenv("REGULATRACE_DB_PATH", str(tmp_path / "regulatrace-test.db"))
    monkeypatch.setenv("REGULATRACE_LEGALBERT", "off")


def test_health_exposes_engine_version() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert {key: value for key, value in payload.items() if key != "legalBert"} == {
        "status": "ok",
        "service": "regulatrace-api",
        "phase": "presentation-edition",
        "engineVersion": "0.4.0-research",
    }
    assert payload["legalBert"]["state"] == "disabled"


def test_openapi_documentation_exposes_all_phase_one_routes() -> None:
    docs_response = client.get("/api/docs")
    schema_response = client.get("/api/openapi.json")
    assert docs_response.status_code == 200
    assert schema_response.status_code == 200
    paths = schema_response.json()["paths"]
    assert {
        "/api/health", "/api/analyze", "/api/compare", "/api/versions/compare",
        "/api/documents/ingest", "/api/analyses", "/api/reviews", "/api/evaluate",
    }.issubset(paths)


def test_analyze_preserves_frontend_contract_and_metadata() -> None:
    response = client.post(
        "/api/analyze",
        json={
            "text": GDPR,
            "sourceMetadata": {
                "sourceId": "eur-lex://gdpr/33",
                "version": "2016-05-04",
                "authority": "European Union",
                "jurisdiction": "EU",
                "section": "Article 33",
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["engineVersion"] == "0.4.0-research"
    assert payload["source"]["sourceId"] == "eur-lex://gdpr/33"
    assert payload["summary"]["citationIntegrity"] == 1
    assert payload["normative"][0]["modality"] == "OBLIGATION"
    assert "72 hours" in payload["normative"][0]["deadline"]
    assert "unlikely" in payload["normative"][0]["exception"]


def test_compare_flags_slower_policy_deadline() -> None:
    policy = "The controller shall notify the supervisory authority no later than 96 hours after confirming a reportable breach."
    response = client.post("/api/compare", json={"regulatoryText": GDPR, "policyText": policy})
    assert response.status_code == 200
    payload = response.json()
    assert payload["outcome"] == "POTENTIAL_MISMATCH"
    assert next(item for item in payload["dimensions"] if item["id"] == "timing")["score"] < 1
    assert payload["modelSignal"]["state"] == "disabled"


def test_legal_bert_signal_is_reported_without_overriding_deadline_gate(monkeypatch) -> None:
    from backend import hybrid

    monkeypatch.setattr(hybrid.legalbert, "model_status", lambda: {"ready": True, "state": "ready", "modelId": "test-legal-bert", "detail": "test"})
    monkeypatch.setattr(hybrid.legalbert, "similarity_matrix", lambda left, right: [[0.98]])
    response = client.post(
        "/api/compare",
        json={
            "regulatoryText": "The controller shall notify the authority within 72 hours after awareness.",
            "policyText": "The controller shall notify the authority within 96 hours after awareness.",
        },
    )
    payload = response.json()
    assert payload["modelSignal"]["state"] == "active"
    assert payload["modelSignal"]["cosineSimilarity"] == 0.98
    assert payload["outcome"] == "POTENTIAL_MISMATCH"


def test_legal_bert_retrieves_relevant_clause_from_longer_policy(monkeypatch) -> None:
    from backend import hybrid

    monkeypatch.setattr(hybrid.legalbert, "model_status", lambda: {"ready": True, "state": "ready", "modelId": "test-legal-bert", "detail": "test"})
    monkeypatch.setattr(hybrid.legalbert, "similarity_matrix", lambda left, right: [[0.95 if "notify" in text else 0.2 for text in right]])
    response = client.post(
        "/api/compare",
        json={
            "regulatoryText": "The controller shall notify the authority within 72 hours after awareness.",
            "policyText": "The controller shall retain incident records for seven years. The controller shall notify the authority within 48 hours after awareness.",
        },
    )
    payload = response.json()
    assert payload["retrieval"]["candidateCount"] == 2
    assert payload["retrieval"]["selectedIndex"] == 1
    assert "notify" in payload["policy"]["evidence"]
    assert payload["modelSignal"]["state"] == "active"


def test_version_compare_detects_modified_and_added_clauses() -> None:
    response = client.post(
        "/api/versions/compare",
        json={
            "oldText": "The organization shall review accounts every 90 days.",
            "newText": "The organization shall review accounts every 60 days. Dormant accounts must be disabled immediately.",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert any(change["type"] == "MODIFIED" for change in payload["changes"])
    assert any(change["type"] == "ADDED" for change in payload["changes"])
    assert payload["criticalCount"] >= 1


def test_legal_bert_can_align_a_paraphrased_clause(monkeypatch) -> None:
    from backend import hybrid

    monkeypatch.setattr(hybrid.legalbert, "model_status", lambda: {"ready": True, "state": "ready", "modelId": "test-legal-bert", "detail": "test"})
    monkeypatch.setattr(hybrid.legalbert, "similarity_matrix", lambda left, right: [[0.8784]])
    response = client.post(
        "/api/versions/compare",
        json={
            "oldText": "The organization shall review privileged user accounts at least once every 90 days.",
            "newText": "The organization must inspect privileged access every 60 days.",
        },
    )
    payload = response.json()
    assert payload["modelSignal"]["state"] == "active"
    assert payload["changes"][0]["type"] == "MODIFIED"
    assert payload["changes"][0]["alignmentMethod"] == "legal-bert"
    assert payload["changes"][0]["semanticSimilarity"] == 0.8784


def test_low_semantic_similarity_does_not_force_a_match(monkeypatch) -> None:
    from backend import hybrid

    monkeypatch.setattr(hybrid.legalbert, "model_status", lambda: {"ready": True, "state": "ready", "modelId": "test-legal-bert", "detail": "test"})
    monkeypatch.setattr(hybrid.legalbert, "similarity_matrix", lambda left, right: [[0.38]])
    response = client.post(
        "/api/versions/compare",
        json={
            "oldText": "The organization shall review privileged user accounts at least once every 90 days.",
            "newText": "The organization must inspect privileged access every 60 days.",
        },
    )
    assert {change["type"] for change in response.json()["changes"]} == {"ADDED", "REMOVED"}


def test_change_rationale_distinguishes_observation_from_inference() -> None:
    response = client.post(
        "/api/versions/compare",
        json={
            "oldText": "The controller shall notify the authority within five days. The organization shall retain incident records for three years.",
            "newText": "The controller shall notify the authority within 72 hours. The organization shall retain incident records for seven years. The controller must document a late notification.",
        },
    )
    assert response.status_code == 200
    changes = response.json()["changes"]
    notification = next(change for change in changes if change["type"] == "MODIFIED" and "notify" in change["after"])
    assert "five days to 72 hours" in notification["explanation"]["observed"]
    assert notification["explanation"]["status"] == "INFERRED_FROM_TEXT"
    assert notification["severity"] == "CRITICAL"
    retention = next(change for change in changes if change["type"] == "MODIFIED" and "retain" in change["after"])
    assert "retention period" in retention["explanation"]["observed"]
    addition = next(change for change in changes if change["type"] == "ADDED")
    assert addition["explanation"]["status"] == "UNDETERMINED"
    assert "cannot be established" in addition["explanation"]["possibleRationale"]


def test_hyphenated_retention_period_is_not_read_as_its_suffix() -> None:
    response = client.post(
        "/api/versions/compare",
        json={
            "oldText": "The security owner shall retain review evidence for twelve months.",
            "newText": "The security owner shall retain review evidence for twenty-four months.",
        },
    )
    assert response.status_code == 200
    explanation = response.json()["changes"][0]["explanation"]
    assert explanation["observed"] == "The retention period changed from twelve months to twenty-four months (extended)."
    assert "preserve records for longer" in explanation["possibleRationale"]


def test_whitespace_input_returns_structured_validation_error() -> None:
    response = client.post("/api/analyze", json={"text": "   ", "sourceMetadata": {}})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_local_frontend_origin_is_allowed_by_cors() -> None:
    response = client.options(
        "/api/analyze",
        headers={
            "Origin": "http://127.0.0.1:4173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:4173"


def test_text_document_ingestion_returns_document_statistics() -> None:
    response = client.post(
        "/api/documents/ingest",
        files={"file": ("rule.txt", b"The provider must retain logs for seven years.", "text/plain")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["filename"] == "rule.txt"
    assert payload["format"] == "TXT"
    assert payload["words"] == 8
    assert "retain logs" in payload["text"]


def test_persisted_analysis_can_be_reviewed_and_restored() -> None:
    created = client.post(
        "/api/analyze",
        json={"text": GDPR, "persist": True, "sourceMetadata": {"title": "GDPR Article 33", "sourceId": "eur-lex://gdpr/33"}},
    )
    assert created.status_code == 200
    analysis = created.json()
    assert analysis["analysisId"].startswith("AN-")
    record_id = analysis["records"][0]["id"]

    reviewed = client.post(
        "/api/reviews",
        json={"analysisId": analysis["analysisId"], "recordId": record_id, "decision": "CONFIRMED", "reviewer": "Test reviewer"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["decision"] == "CONFIRMED"

    restored = client.get(f"/api/analyses/{analysis['analysisId']}")
    history = client.get("/api/analyses")
    audit = client.get(f"/api/analyses/{analysis['analysisId']}/audit")
    assert restored.json()["records"][0]["reviewState"] == "CONFIRMED"
    assert history.json()[0]["reviewedCount"] == 1
    assert audit.json()[0]["reviewer"] == "Test reviewer"


def test_executable_evaluation_reports_transparent_case_results() -> None:
    response = client.get("/api/evaluate")
    assert response.status_code == 200
    payload = response.json()
    assert payload["datasetType"] == "synthetic-adversarial"
    assert payload["executedCases"] == 16
    assert payload["passedCases"] <= payload["executedCases"]
    assert 0 <= payload["metrics"]["criticalMissRate"] <= 1


def test_fastapi_serves_the_presentation_frontend() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "RegulaTrace" in response.text
    assert "Executive Brief" in response.text

