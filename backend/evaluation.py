"""Executable, transparent synthetic benchmark for the Evaluation Console."""

from __future__ import annotations

from typing import Any

from backend.engine import analyze_document, compare_policy, compare_versions


EXTRACTION_CASES = [
    ("The provider must retain security logs for seven years.", "OBLIGATION", "provider", None),
    ("The controller shall notify the authority within 72 hours after awareness.", "OBLIGATION", "controller", "72 hours"),
    ("The processor must not disclose personal data to unauthorized parties.", "PROHIBITION", "processor", None),
    ("The board should review the risk register quarterly.", "RECOMMENDATION", "board", "quarterly"),
    ("The operator may suspend access where misuse is detected.", "PERMISSION", "operator", None),
    ("Records may not be complete when the migration begins.", "INFORMATION", None, None),
    ("The security owner shall remediate critical findings within 30 days of discovery.", "OBLIGATION", "security owner", "30 days"),
    ("The institution is required to report material incidents immediately.", "OBLIGATION", "institution", "immediately"),
    ("Vendors are prohibited from sharing credentials.", "PROHIBITION", "vendors", None),
    ("The auditor ought to document the sampling method.", "RECOMMENDATION", "auditor", None),
    ("The authority may request additional evidence.", "PERMISSION", "authority", None),
    ("The organization shall test backups at least once every 90 days.", "OBLIGATION", "organization", "90 days"),
]

# A critical miss is a missed or materially misread duty, serious policy mismatch,
# or material version change. Other failed checks still lower the overall pass rate.
CRITICAL_EXTRACTION_CASES = {2, 3, 7, 8, 9, 12}

COMPARISON_CASES = [
    (
        "The controller shall notify the authority within 72 hours after awareness.",
        "The controller shall notify the authority within 48 hours after awareness.",
        "LIKELY_ALIGNED",
    ),
    (
        "The controller shall notify the authority within 72 hours after awareness.",
        "The controller shall notify the authority within 96 hours after confirmation.",
        "POTENTIAL_MISMATCH",
    ),
    (
        "The processor must not disclose personal data.",
        "The processor may disclose personal data to approved partners.",
        "POTENTIAL_MISMATCH",
    ),
]


def run_benchmark() -> dict[str, Any]:
    extraction_results = []
    for index, (text, modality, actor_fragment, deadline_fragment) in enumerate(EXTRACTION_CASES, start=1):
        analysis = analyze_document(text, {"sourceId": f"benchmark://case/{index}", "section": f"Case {index}"})
        record = analysis["records"][0] if analysis["records"] else None
        modality_ok = bool(record and record["modality"] == modality)
        actor_ok = actor_fragment is None or bool(record and actor_fragment.lower() in record["actor"].lower())
        deadline_ok = deadline_fragment is None or bool(record and record["deadline"] and deadline_fragment.lower() in record["deadline"].lower())
        span = record["sourceSpan"] if record else None
        provenance_ok = bool(record and span and text[span["start"]:span["end"]] == text and record["sourceId"].startswith("benchmark://"))
        passed = modality_ok and actor_ok and deadline_ok and provenance_ok
        critical = index in CRITICAL_EXTRACTION_CASES
        extraction_results.append(
            {
                "id": f"EX-{index:02d}",
                "passed": passed,
                "expected": modality,
                "observed": record["modality"] if record else "MISSED",
                "checks": {"modality": modality_ok, "actor": actor_ok, "deadline": deadline_ok, "provenance": provenance_ok},
                "critical": critical,
                "criticalMiss": critical and not (modality_ok and actor_ok and deadline_ok),
            }
        )

    comparison_results = []
    for index, (requirement, policy, expected) in enumerate(COMPARISON_CASES, start=1):
        result = compare_policy(requirement, policy)
        critical = expected == "POTENTIAL_MISMATCH"
        comparison_results.append({
            "id": f"CP-{index:02d}", "passed": result["outcome"] == expected,
            "expected": expected, "observed": result["outcome"],
            "critical": critical, "criticalMiss": critical and result["outcome"] != expected,
        })

    version_result = compare_versions(
        "The organization shall review accounts every 90 days.",
        "The organization shall review accounts every 60 days. Dormant accounts must be disabled immediately.",
    )
    version_passed = any(item["type"] == "MODIFIED" for item in version_result["changes"]) and any(
        item["type"] == "ADDED" for item in version_result["changes"]
    )
    passed = sum(item["passed"] for item in extraction_results) + sum(item["passed"] for item in comparison_results) + int(version_passed)
    total = len(extraction_results) + len(comparison_results) + 1
    modality_accuracy = sum(item["checks"]["modality"] for item in extraction_results) / len(extraction_results)
    provenance_integrity = sum(item["checks"]["provenance"] for item in extraction_results) / len(extraction_results)
    deadline_cases = [item for item, source in zip(extraction_results, EXTRACTION_CASES) if source[3] is not None]
    deadline_accuracy = sum(item["checks"]["deadline"] for item in deadline_cases) / len(deadline_cases)
    critical_cases = [*extraction_results, *comparison_results, {"critical": True, "criticalMiss": not version_passed}]
    critical_cases = [item for item in critical_cases if item["critical"]]
    return {
        "benchmark": "RegulaTrace transparent challenge suite v1",
        "datasetType": "synthetic-adversarial",
        "executedCases": total,
        "passedCases": passed,
        "passRate": passed / total,
        "metrics": {
            "modalityAccuracy": modality_accuracy,
            "deadlineAccuracy": deadline_accuracy,
            "provenanceIntegrity": provenance_integrity,
            "criticalMissRate": sum(item["criticalMiss"] for item in critical_cases) / len(critical_cases),
            "criticalCaseCount": float(len(critical_cases)),
        },
        "suites": {
            "extraction": extraction_results,
            "comparison": comparison_results,
            "versioning": [{"id": "VR-01", "passed": version_passed, "observedChanges": len(version_result["changes"]), "critical": True, "criticalMiss": not version_passed}],
        },
    }
