"""Typed API contracts for the RegulaTrace deterministic backend."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class APIModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class SourceMetadata(APIModel):
    source_id: str | None = Field(default=None, alias="sourceId")
    version: str | None = None
    authority: str | None = None
    jurisdiction: str | None = None
    section: str | None = None
    title: str | None = None


class AnalyzeRequest(APIModel):
    text: str = Field(min_length=1, max_length=250_000)
    source_metadata: SourceMetadata = Field(default_factory=SourceMetadata, alias="sourceMetadata")
    persist: bool = False

    @field_validator("text")
    @classmethod
    def text_must_contain_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must contain non-whitespace content")
        return value


class CompareRequest(APIModel):
    regulatory_text: str = Field(alias="regulatoryText", min_length=1, max_length=250_000)
    policy_text: str = Field(alias="policyText", min_length=1, max_length=250_000)

    @field_validator("regulatory_text", "policy_text")
    @classmethod
    def texts_must_contain_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("comparison text must contain non-whitespace content")
        return value


class VersionCompareRequest(APIModel):
    old_text: str = Field(alias="oldText", min_length=1, max_length=250_000)
    new_text: str = Field(alias="newText", min_length=1, max_length=250_000)

    @field_validator("old_text", "new_text")
    @classmethod
    def versions_must_contain_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("version text must contain non-whitespace content")
        return value


Modality = Literal["PROHIBITION", "OBLIGATION", "RECOMMENDATION", "PERMISSION", "INFORMATION"]


class ObligationRecord(APIModel):
    id: str
    source_id: str = Field(alias="sourceId")
    source_version: str = Field(alias="sourceVersion")
    authority: str
    jurisdiction: str
    section: str
    modality: Modality
    modality_cue: str = Field(alias="modalityCue")
    modality_confidence: float = Field(alias="modalityConfidence")
    actor: str
    action: str
    deadline: str | None
    condition: str | None
    exception: str | None
    cross_references: list[str] = Field(alias="crossReferences")
    evidence: str
    review_state: str = Field(alias="reviewState")
    severity: Literal["HIGH", "MEDIUM", "STANDARD"]
    unresolved: list[str]
    confidence: float


class AnalysisSummary(APIModel):
    clause_count: int = Field(alias="clauseCount")
    obligation_count: int = Field(alias="obligationCount")
    unresolved_count: int = Field(alias="unresolvedCount")
    avg_confidence: float = Field(alias="avgConfidence")
    citation_integrity: float = Field(alias="citationIntegrity")
    modality_counts: dict[str, int] = Field(alias="modalityCounts")


class AnalysisResponse(APIModel):
    analysis_id: str | None = Field(default=None, alias="analysisId")
    engine_version: str = Field(alias="engineVersion")
    analyzed_at: str = Field(alias="analyzedAt")
    source: SourceMetadata
    records: list[ObligationRecord]
    normative: list[ObligationRecord]
    summary: AnalysisSummary


class ComparisonDimension(APIModel):
    id: str
    label: str
    score: float
    detail: str


class ModelSignal(APIModel):
    state: Literal["disabled", "setup-required", "ready", "active", "error"]
    ready: bool | None = None
    model_id: str = Field(alias="modelId")
    detail: str
    cosine_similarity: float | None = Field(default=None, alias="cosineSimilarity")


class RetrievalInfo(APIModel):
    candidate_count: int = Field(alias="candidateCount")
    considered_count: int = Field(alias="consideredCount")
    selected_index: int = Field(alias="selectedIndex")
    selected_clause: str = Field(alias="selectedClause")
    method: Literal["hybrid-legal-bert-lexical"]


class ComparisonResponse(APIModel):
    requirement: ObligationRecord | None
    policy: ObligationRecord | None
    dimensions: list[ComparisonDimension]
    score: float
    outcome: Literal["POTENTIAL_MISMATCH", "LIKELY_ALIGNED", "REVIEW_REQUIRED"]
    lexical_similarity: float = Field(alias="lexicalSimilarity")
    model_signal: ModelSignal | None = Field(default=None, alias="modelSignal")
    retrieval: RetrievalInfo | None = None


class ChangeExplanation(APIModel):
    observed: str
    possible_rationale: str = Field(alias="possibleRationale")
    operational_impact: str = Field(alias="operationalImpact")
    status: Literal["INFERRED_FROM_TEXT", "UNDETERMINED"]


class VersionChange(APIModel):
    id: str
    type: Literal["MODIFIED", "ADDED", "REMOVED"]
    before: str | None
    after: str | None
    similarity: float
    severity: Literal["CRITICAL", "MATERIAL"]
    explanation: ChangeExplanation
    alignment_method: Literal["lexical", "legal-bert", "none"] | None = Field(default=None, alias="alignmentMethod")
    semantic_similarity: float | None = Field(default=None, alias="semanticSimilarity")


class VersionCompareResponse(APIModel):
    changes: list[VersionChange]
    counts: dict[str, int]
    affected_obligations: int = Field(alias="affectedObligations")
    critical_count: int = Field(alias="criticalCount")
    materiality_score: int = Field(alias="materialityScore")
    model_signal: ModelSignal | None = Field(default=None, alias="modelSignal")


class HealthResponse(APIModel):
    status: Literal["ok"]
    service: str
    phase: str
    engine_version: str = Field(alias="engineVersion")
    legal_bert: ModelSignal = Field(alias="legalBert")


class IngestResponse(APIModel):
    filename: str
    format: str
    text: str
    characters: int
    words: int
    pages: int


class ReviewRequest(APIModel):
    analysis_id: str = Field(alias="analysisId", min_length=3, max_length=64)
    record_id: str = Field(alias="recordId", min_length=3, max_length=128)
    decision: Literal["CONFIRMED", "CORRECTED", "REJECTED"]
    note: str | None = Field(default=None, max_length=2_000)
    reviewer: str = Field(default="Presentation reviewer", min_length=2, max_length=120)


class ReviewResponse(APIModel):
    analysis_id: str = Field(alias="analysisId")
    record_id: str = Field(alias="recordId")
    decision: str
    reviewer: str
    note: str | None
    created_at: str = Field(alias="createdAt")
    reviewed_count: int = Field(alias="reviewedCount")


class AnalysisHistoryItem(APIModel):
    analysis_id: str = Field(alias="analysisId")
    created_at: str = Field(alias="createdAt")
    source_title: str = Field(alias="sourceTitle")
    authority: str
    jurisdiction: str
    record_count: int = Field(alias="recordCount")
    unresolved_count: int = Field(alias="unresolvedCount")
    reviewed_count: int = Field(alias="reviewedCount")


class AuditEvent(APIModel):
    record_id: str = Field(alias="recordId")
    decision: str
    note: str | None
    reviewer: str
    created_at: str = Field(alias="createdAt")


class DashboardResponse(APIModel):
    analyses: int
    records: int
    unresolved: int
    reviewed: int
    decisions: dict[str, int]
    database: str


class BenchmarkResponse(APIModel):
    benchmark: str
    dataset_type: str = Field(alias="datasetType")
    executed_cases: int = Field(alias="executedCases")
    passed_cases: int = Field(alias="passedCases")
    pass_rate: float = Field(alias="passRate")
    metrics: dict[str, float]
    suites: dict[str, list[dict[str, Any]]]


class GroundingFact(APIModel):
    subject: str = Field(min_length=2, max_length=120)
    relation: Literal["IS_A", "SAME_AS"]
    object: str = Field(min_length=2, max_length=120)


class ContradictionClause(APIModel):
    id: str = Field(min_length=2, max_length=50)
    text: str = Field(min_length=12, max_length=8_000)
    authority: str = Field(default="User supplied", max_length=120)
    citation: str = Field(default="Unspecified clause", max_length=160)
    source_url: str | None = Field(default=None, alias="sourceUrl", max_length=500)
    effective_from: date | None = Field(default=None, alias="effectiveFrom")
    actor_hint: str | None = Field(default=None, alias="actorHint", max_length=120)
    entity_hint: str | None = Field(default=None, alias="entityHint", max_length=120)

    @field_validator("source_url")
    @classmethod
    def source_url_must_be_http(cls, value: str | None) -> str | None:
        if value and not value.startswith(("https://", "http://")):
            raise ValueError("sourceUrl must be an HTTP or HTTPS URL")
        return value


class ContradictionContext(APIModel):
    as_of: date = Field(alias="asOf")
    event_date: date | None = Field(default=None, alias="eventDate")
    target_actor: str = Field(alias="targetActor", min_length=2, max_length=120)
    target_entity: str = Field(alias="targetEntity", min_length=2, max_length=120)
    purpose_ended: bool = Field(default=True, alias="purposeEnded")
    facts: list[GroundingFact] = Field(default_factory=list, max_length=30)


class ContradictionRequest(APIModel):
    clauses: list[ContradictionClause] = Field(min_length=2, max_length=6)
    context: ContradictionContext


class NormTuple(APIModel):
    id: str
    source_id: str = Field(alias="sourceId")
    source_url: str | None = Field(alias="sourceUrl")
    actor: str
    action: Literal["ERASE", "RETAIN", "OTHER"]
    modality: Literal["O", "F", "P", "UNKNOWN"]
    entity: str
    scope: str
    duration_days: int | None = Field(alias="durationDays")
    exception: str | None
    evidence: str
    extraction_method: str = Field(alias="extractionMethod")
    status: Literal["ACTIVE", "INACTIVE", "EXCEPTED", "UNRESOLVED", "OUT_OF_SCOPE"]
    reason: str


class ProofResult(APIModel):
    solver: str
    check: Literal["sat", "unsat", "unknown", "not-run"]
    constraints: list[str]
    unsat_core: list[str] = Field(alias="unsatCore")
    witness: str | None


class GraphNode(APIModel):
    id: str
    label: str
    type: Literal["actor", "entity", "source", "norm"]


class GraphEdge(APIModel):
    source: str
    target: str
    label: str


class ContradictionGraph(APIModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    backend: Literal["neo4j", "in-memory"]
    detail: str


class PipelineStage(APIModel):
    name: str
    state: Literal["active", "rules", "not-configured", "offline", "error"]
    detail: str


class ContradictionResponse(APIModel):
    verdict: Literal["SAT", "UNSAT", "INDETERMINATE"]
    summary: str
    tuples: list[NormTuple]
    proof: ProofResult
    graph: ContradictionGraph
    stages: list[PipelineStage]
    assumptions: list[str]
    neural_similarity: float | None = Field(alias="neuralSimilarity")
    dspy_suggestions: list[dict[str, str]] = Field(default_factory=list, alias="dspySuggestions")


class ContradictionExample(APIModel):
    id: str
    title: str
    subtitle: str
    request: ContradictionRequest


class SourcePrecisionRequest(APIModel):
    retrieved_context_ids: list[str] = Field(alias="retrievedContextIds", max_length=500)
    reference_context_ids: list[str] = Field(alias="referenceContextIds", max_length=500)


class SourcePrecisionResponse(APIModel):
    precision: float = Field(ge=0, le=1)
    backend: Literal["ragas", "deterministic", "error"]
    detail: str


class ErrorBody(APIModel):
    code: str
    message: str
    details: Any | None = None


class ErrorResponse(APIModel):
    error: ErrorBody

