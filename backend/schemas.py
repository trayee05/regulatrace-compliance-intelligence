"""Typed API contracts for the RegulaTrace deterministic backend."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


class SourceSpan(APIModel):
    start: int = Field(ge=0)
    end: int = Field(ge=0)


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
    source_span: SourceSpan | None = Field(default=None, alias="sourceSpan")
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


class ComparisonResponse(APIModel):
    requirement: ObligationRecord | None
    policy: ObligationRecord | None
    dimensions: list[ComparisonDimension]
    score: float
    outcome: Literal["POTENTIAL_MISMATCH", "LIKELY_ALIGNED", "REVIEW_REQUIRED"]
    lexical_similarity: float = Field(alias="lexicalSimilarity")


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


class VersionCompareResponse(APIModel):
    changes: list[VersionChange]
    counts: dict[str, int]
    affected_obligations: int = Field(alias="affectedObligations")
    critical_count: int = Field(alias="criticalCount")
    materiality_score: int = Field(alias="materialityScore")


class HealthResponse(APIModel):
    status: Literal["ok"]
    service: str
    phase: str
    engine_version: str = Field(alias="engineVersion")


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
    corrected_fields: dict[Literal["actor", "action", "modality", "deadline", "condition", "exception"], str | None] = Field(default_factory=dict, alias="correctedFields")

    @model_validator(mode="after")
    def correction_must_change_fields(self) -> "ReviewRequest":
        if self.decision == "CORRECTED" and not self.corrected_fields:
            raise ValueError("a corrected review must supply correctedFields")
        if self.decision != "CORRECTED" and self.corrected_fields:
            raise ValueError("correctedFields are only accepted for a corrected review")
        for field, value in self.corrected_fields.items():
            if field in {"actor", "action", "modality"} and (value is None or not value.strip()):
                raise ValueError(f"{field} cannot be empty")
            if value is not None and len(value) > 2_000:
                raise ValueError(f"{field} is too long")
        if "modality" in self.corrected_fields and self.corrected_fields["modality"] not in {"PROHIBITION", "OBLIGATION", "RECOMMENDATION", "PERMISSION", "INFORMATION"}:
            raise ValueError("modality is invalid")
        return self


class ReviewResponse(APIModel):
    analysis_id: str = Field(alias="analysisId")
    record_id: str = Field(alias="recordId")
    decision: str
    reviewer: str
    note: str | None
    created_at: str = Field(alias="createdAt")
    reviewed_count: int = Field(alias="reviewedCount")
    changes: dict[str, dict[str, str | None]] = Field(default_factory=dict)


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
    changes: dict[str, dict[str, str | None]] = Field(default_factory=dict)


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


class ErrorBody(APIModel):
    code: str
    message: str
    details: Any | None = None


class ErrorResponse(APIModel):
    error: ErrorBody

