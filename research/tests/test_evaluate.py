import json

import pytest

from research.evaluate import evaluate, load_gold


def _write(tmp_path, documents):
    path = tmp_path / "gold.jsonl"
    path.write_text("\n".join(json.dumps(document) for document in documents), encoding="utf-8")
    return path


def test_held_out_evaluation_counts_true_and_false_positives(tmp_path):
    duty = "The provider must retain logs."
    documents = [
        {"document_id": "a", "source_id": "source-a", "split": "test", "text": duty,
         "annotations": [{"start": 0, "end": len(duty), "modality": "OBLIGATION", "critical": True}]},
        {"document_id": "b", "source_id": "source-b", "split": "test", "text": "The operator must protect records.", "annotations": []},
    ]
    report = evaluate(load_gold(_write(tmp_path, documents)))
    assert report["candidate_detection"] == {"tp": 1, "fp": 1, "fn": 0, "precision": 0.5, "recall": 1.0, "f1": 2 / 3}
    assert report["critical_miss_rate"] == 0
    assert report["invalid_provenance_count"] == 0
    assert any(error["type"] == "false_positive" for error in report["errors"])


def test_wrong_modality_counts_as_critical_miss(tmp_path):
    text = "The provider may retain logs."
    document = {"document_id": "a", "source_id": "source-a", "split": "test", "text": text,
                "annotations": [{"start": 0, "end": len(text), "modality": "OBLIGATION", "critical": True}]}
    report = evaluate(load_gold(_write(tmp_path, [document])))
    assert report["candidate_detection"]["tp"] == 1
    assert report["modality_accuracy_on_matched"] == 0
    assert report["critical_miss_rate"] == 1
    assert report["errors"][0]["type"] == "wrong_modality"


def test_gold_loader_rejects_source_leakage(tmp_path):
    documents = [
        {"document_id": "a", "source_id": "same-source", "split": "train", "text": "The provider must retain logs.", "annotations": []},
        {"document_id": "b", "source_id": "same-source", "split": "test", "text": "The provider must secure logs.", "annotations": []},
    ]
    with pytest.raises(ValueError, match="crosses splits"):
        load_gold(_write(tmp_path, documents))


def test_gold_loader_rejects_overlapping_spans(tmp_path):
    text = "The provider must retain logs."
    document = {"document_id": "a", "source_id": "source-a", "split": "test", "text": text,
                "annotations": [
                    {"start": 0, "end": 20, "modality": "OBLIGATION", "critical": True},
                    {"start": 10, "end": len(text), "modality": "OBLIGATION", "critical": False},
                ]}
    with pytest.raises(ValueError, match="must not overlap"):
        load_gold(_write(tmp_path, [document]))
