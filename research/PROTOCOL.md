# RegulaTrace held-out obligation study

This protocol defines the first research evaluation. The bundled 16-case challenge suite is a development smoke test; its score is not a paper result. No held-out corpus or model comparison result is included in this repository.

## Research question

How often does the deterministic baseline detect the right regulatory duty, preserve its text location, and classify its modality on unseen documents? The primary safety measure is the miss rate among independently labeled critical duties.

## Corpus and split

Collect source documents with a stable public URL, issuing authority, jurisdiction, publication date, retrieved snapshot, and license or reuse note. Store the exact extracted text used for annotation. Keep all versions and related sections of an instrument under one `source_id`; do not place that source in more than one split. Split by source before model development. Freeze the test split and its annotation guide before looking at test predictions.

The evaluator rejects repeated document IDs, the same source ID across splits, and identical normalized text across splits. These checks catch common leakage, but a researcher must still check near-duplicate instruments manually.

## Annotation

Use JSON Lines, one document per line. Offsets are Unicode code-point positions in `text`; `end` is exclusive. Annotate the shortest complete clause that expresses a normative duty, prohibition, permission, or recommendation, including any timing and exception text needed to interpret it. A descriptive statement has no annotation. Do not annotate the same character range twice. A section with no duties has an empty `annotations` list and remains useful for precision measurement.

```json
{"document_id":"example-001","source_id":"fictional://rulebook-a","split":"test","text":"The provider must retain logs.","annotations":[{"start":0,"end":30,"modality":"OBLIGATION","critical":true}]}
```

The example is fictional and only illustrates the format. Add optional metadata such as `jurisdiction` and `authority` in separate keys. Treat `source_id` as the leakage group, not a unique section ID. Set `critical` before seeing model output. A critical duty is one whose omission could materially change a deadline, reporting requirement, prohibition, or high-consequence control. Record the reason in the annotation worksheet; the evaluator consumes the Boolean label.

Two annotators should label each test document independently. Adjudicate disagreements without viewing model output and publish the initial agreement rate, adjudication count, and final annotation guide. Preserve the unadjudicated labels for analysis. Do not silently change gold labels after inspecting errors.

## Evaluation command and metric definitions

Run `python -m research.evaluate path/to/gold.jsonl --split test`. The command prints JSON with counts and error rows. Predictions come from the deterministic Python engine at the current `engineVersion`. Pin the Git commit, dependency versions, and text-extraction method when reporting results.

Candidate detection matches predicted and gold spans one to one by descending intersection-over-union, requiring at least 0.5 overlap. Unmatched gold spans are false negatives; unmatched predictions are false positives. Precision, recall, and F1 use those counts. Modality accuracy is measured on matched spans. Critical miss rate is the share of gold critical duties that are unmatched or have the wrong modality. It is `null` when the test set has no critical duties. Provenance validity checks whether each predicted span maps back to the supplied text and its retained evidence clause.

Report raw numerators and denominators, not just rounded percentages. Inspect every error row, especially critical misses. Use a document-level bootstrap for confidence intervals once the corpus is large enough. Do not select thresholds, rules, or prompts using the test split.

## Current limits and next gates

This harness evaluates candidate location and modality. Actor, action, deadline anchor, exception span, policy-gap classification, change impact, calibration, and reviewer time need additional gold fields and blinded studies before making comparative claims. The next gate is a pilot of at least 20 diverse source documents to test the annotation guide and offset consistency, followed by a frozen held-out set. The pilot size is a workflow target, not an existing dataset.
