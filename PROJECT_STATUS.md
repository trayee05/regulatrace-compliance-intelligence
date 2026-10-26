# RegulaTrace Project Status

Status date: 2026-10-26
Current milestone: Presentation Edition — integrated full-stack research demonstrator

## Verified result

- FastAPI and frontend run together at `http://127.0.0.1:8000`.
- Backend integration tests and JavaScript engine tests cover extraction, comparison, version analysis, and change explanations.
- The executable challenge suite passed 16 of 16 transparent synthetic-adversarial cases, with 0% critical misses on that suite.
- Browser verification rendered three evidence-linked obligations, persisted a field correction, restored the reviewed case, and confirmed its before/after audit event.
- Backend and research tests passed locally (20 tests); JavaScript engine tests passed (8 tests). [CI passed on the fork branch](https://github.com/lakshitsachdeva/regulatrace-compliance-intelligence/actions/runs/40361949647); the upstream draft PR has not reported checks.

## Implemented

### Complete application experience

- Executive Brief with live KPIs, research-readiness indicators, a presentation narrative, printable briefing, and one-click end-to-end demo.
- Obligation Lab, Evidence Graph, Policy Comparator, Change Radar, Evaluation Console, guided examples, keyboard command palette, responsive navigation, and presentation mode.
- Clear backend connection status and an explicitly labeled browser-engine fallback.

### Backend and data layer

- FastAPI service with typed Pydantic request and response contracts, structured errors, CORS configuration, OpenAPI, and ReDoc.
- Static frontend served by FastAPI so the full project uses one local server.
- Deterministic Python implementation compatible with the existing JavaScript response structure.
- SQLite persistence for analyses, extracted records, reviewer decisions, and audit events.
- Reviewer field corrections store before/after values and preserve the original evidence clause.
- Case history, case restoration, live dashboard totals, and decision-state aggregation.
- Text extraction from text-based PDF, DOCX, TXT, and Markdown uploads, with file type, size, and extraction validation.

### Analysis and evaluation

- Evidence-linked obligation extraction with actor, action, modality, deadlines, conditions, exceptions, references, confidence, unresolved fields, and exact character offsets into the supplied text.
- Constraint-level policy comparison with an explicit verdict and dimension-by-dimension evidence.
- Old/new regulatory version comparison with added, removed, and modified clause classification.
- Change explanations that state the observed edit, a possible rationale when wording supports one, and an operational action to review. Unknown motives are labeled as such.
- Executable 16-case transparent challenge suite covering extraction, modality, actor, deadlines, provenance, policy comparison, and versioning.
- Held-out JSONL evaluation harness validates gold offsets and split leakage, then reports detection F1, matched modality accuracy, critical misses, provenance errors, and an error list. No held-out corpus is bundled.
- Exploratory external sentence-classification experiments now compare the rules with TF-IDF logistic regression and SVM baselines on two independently released EU datasets. The scripts, cleaning audit, fold metrics, and figures are in `research/experiments/`; these do not measure full obligation-span extraction.
- Persistent human review decisions: confirmed, corrected, and rejected.

### Delivery and quality

- One-click Windows launcher and clean shutdown script.
- Foreground macOS/Linux launcher that creates a virtual environment and starts the local server.
- Automatic environment creation, dependency checking, server startup, health validation, and browser opening.
- Backend tests, JavaScript tests, and JavaScript syntax validation.
- A two-page fictional demonstration regulation in `examples/` for document upload.
- Ignored runtime database, logs, virtual environment, test cache, and other generated state.

## Honest research and production boundaries

These boundaries do not prevent the presentation workflow from running; they define the next credible research and production milestones.

- Scanned/image-only PDFs require OCR before ingestion. Current PDF support extracts embedded text.
- The persistent store is local, single-user SQLite. A deployed multi-user edition would add identity, role-based access, concurrent workflows, encryption policy, backups, and retention controls.
- The deterministic engine is an explainable baseline rather than a semantic legal-language model. Deep paraphrase, inherited headings, complex tables, and heavily nested drafting can require reviewer correction.
- Deadline normalization does not yet resolve business-day calendars, holidays, or jurisdiction-specific counting rules.
- Policy comparison and version alignment remain lexical and constraint-based; the interface deliberately exposes uncertainty instead of claiming legal certainty.
- Change rationales are textual inferences, not evidence of the regulator's actual intent; official explanatory material is not ingested automatically.
- The included benchmark is transparent and synthetic-adversarial, not an external peer-reviewed legal corpus. Paper claims should be based on a separately annotated, document-level held-out dataset with inter-annotator agreement.
- The held-out evaluator and annotation protocol are implemented, but there is no annotated document corpus or inter-annotator agreement result yet.
- The `citationIntegrity` field checks evidence, source-ID, and located source-span presence; source authority and PDF page coordinates are not verified.
- The application supports decision review and evidence traceability but is not legal advice, a compliance certificate, or an autonomous release authority.

## Paper-ready next study

1. Build an expert-annotated, jurisdiction-balanced corpus with document-level train/dev/test splits.
2. Measure field-level span F1, critical-miss rate, provenance validity, calibration, comparison macro F1, change-impact recall, and reviewer-time reduction.
3. Compare this deterministic baseline with n-gram, legal-domain encoder, and constrained language-model systems.
4. Run blinded reviewer studies and report error taxonomies, confidence intervals, ablations, and cross-jurisdiction generalization.
5. Preserve the existing evidence contract so every learned result remains attributable and reviewable.
