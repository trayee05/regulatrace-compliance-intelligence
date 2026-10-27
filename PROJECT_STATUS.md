# RegulaTrace Project Status

Status date: 2026-10-27
Current milestone: Presentation Edition with scoped neuro-symbolic contradiction proofs

## Verified result

- FastAPI and frontend run together at `http://127.0.0.1:8000`.
- 28 backend integration tests and 7 JavaScript engine tests pass on 2026-10-27 (using a project-local pytest temp directory).
- The live Contradiction Lab API returned SAT for the DPDP/RBI example and UNSAT for the synthetic deadlock; Z3's unsat core identified both demo rules. The local InLegalBERT checkpoint ran on both requests, and the browser displayed the official-source SAT result.
- The locally downloaded LEGAL-BERT-SMALL checkpoint ran through both live API endpoints: it selected the relevant second policy clause and aligned a paraphrased review clause as a modification. The browser displayed the model state and evidence.
- The executable challenge suite passed 16 of 16 transparent synthetic-adversarial cases, with 0% critical misses on that suite.
- Browser verification completed the live story, rendered three evidence-linked obligations, persisted one analysis and one reviewer decision, restored the case history, and produced no console errors.

## Implemented

### Complete application experience

- Executive Brief with live KPIs, research-readiness indicators, a presentation narrative, printable briefing, and one-click end-to-end demo.
- Obligation Lab, Evidence Graph, Policy Comparator, Change Radar, Evaluation Console, guided examples, keyboard command palette, responsive navigation, and presentation mode.
- Contradiction Lab with paired legal clauses, effective dates, citations and source URLs, scenario dates, explicit graph links, five-step execution display, full proof trace, source-linked tuple cards, and JSON export.
- Clear backend connection status and an explicitly labeled browser-engine fallback.

### Backend and data layer

- FastAPI service with typed Pydantic request and response contracts, structured errors, CORS configuration, OpenAPI, and ReDoc.
- Static frontend served by FastAPI so the full project uses one local server.
- Deterministic Python implementation compatible with the existing JavaScript response structure.
- SQLite persistence for analyses, extracted records, reviewer decisions, and audit events.
- Case history, case restoration, live dashboard totals, and decision-state aggregation.
- Text extraction from text-based PDF, DOCX, TXT, and Markdown uploads, with file type, size, and extraction validation.

### Analysis and evaluation

- Evidence-linked obligation extraction with actor, action, modality, deadlines, conditions, exceptions, references, confidence, unresolved fields, and source spans.
- Constraint-level policy comparison with an explicit verdict and dimension-by-dimension evidence.
- Old/new regulatory version comparison with added, removed, and modified clause classification.
- Change explanations that state the observed edit, a possible rationale when wording supports one, and an operational action to review. Unknown motives are labeled as such.
- Optional LEGAL-BERT-SMALL inference for retrieval of a relevant clause from a multi-clause policy and conservative paraphrased clause alignment, with model state and raw cosine scores reported explicitly.
- Executable 16-case transparent challenge suite covering extraction, modality, actor, deadlines, provenance, policy comparison, and versioning.
- Persistent human review decisions: confirmed, corrected, and rejected.
- Typed deontic tuple extraction for erase/retain clauses and contextual actor, entity, duration, and exception checks.
- Z3 SAT/UNSAT/indeterminate verdicts with tracked constraints and source-linked unsat cores. An ungrounded clause prevents a false compatibility conclusion.
- Local InLegalBERT encoder inference for advisory entity similarity. This pretrained checkpoint is not represented as a trained NER model or a legal oracle.
- Optional Neo4j graph persistence; the full graph remains inspectable in memory when Neo4j is not configured.
- A primary-source-linked DPDP/RBI example that correctly models legal retention and commencement timing, plus a clearly synthetic provable deadlock.

### Delivery and quality

- One-click Windows launcher and clean shutdown script.
- Automatic environment creation, dependency checking, server startup, health validation, and browser opening.
- Backend tests, JavaScript tests, and JavaScript syntax validation.
- A two-page fictional demonstration regulation in `examples/` for document upload.
- Ignored runtime database, logs, virtual environment, test cache, and other generated state.
- Separate, reproducible Legal-BERT setup; model weights remain outside Git.
- Separate, reproducible InLegalBERT setup; model weights remain outside Git.

## Honest research and production boundaries

These boundaries do not prevent the presentation workflow from running; they define the next credible research and production milestones.

- Scanned/image-only PDFs require OCR before ingestion. Current PDF support extracts embedded text.
- The persistent store is local, single-user SQLite. A deployed multi-user edition would add identity, role-based access, concurrent workflows, encryption policy, backups, and retention controls.
- The deterministic engine remains an explainable baseline. Legal-BERT assists matching only when locally installed; it is a pretrained encoder, not a fine-tuned obligation extractor. Inherited headings, complex tables, and heavily nested drafting can require reviewer correction.
- Deadline normalization does not yet resolve business-day calendars, holidays, or jurisdiction-specific counting rules.
- The policy verdict remains constraint-based; Legal-BERT's raw cosine is an uncalibrated diagnostic. Change Radar uses a conservative neural matching threshold, which requires evaluation on an annotated legal corpus before any recall or precision claim.
- Change rationales are textual inferences, not evidence of the regulator's actual intent; official explanatory material is not ingested automatically.
- The included benchmark is transparent and synthetic-adversarial, not an external peer-reviewed legal corpus. Paper claims should be based on a separately annotated, document-level held-out dataset with inter-annotator agreement.
- The existing 16-case benchmark measures the deterministic baseline, not Legal-BERT quality. The current neural matching threshold is provisional and English-only; embeddings truncate each clause at 256 tokens. Policy retrieval considers at most 64 clauses and compares the first regulatory requirement. A held-out annotated pair set is needed before reporting neural precision or recall.
- The application supports decision review and evidence traceability but is not legal advice, a compliance certificate, or an autonomous release authority.
- **Poster-component status:** clause input, typed deontic extraction, explicit knowledge graph grounding, Z3 satisfiability check, proof trace, and SAT/UNSAT verdict are live. InLegalBERT runs locally as an advisory encoder, not NER. Neo4j persistence works when an external Neo4j instance is configured; it was not available for a live integration check on this machine. DSPy review-candidate and Ragas source-ID precision adapters are implemented but not configured or claimed as active in the default proof; the UI reports this. A held-out Indian-regulation corpus and human adjudication remain research work.
- The solver currently models one erase/retain decision for a selected actor, record and date. It does not formalize full statutory hierarchies, all exceptions, business-day calendars, or every Indian regulatory clause.

## Paper-ready next study

1. Build an expert-annotated, jurisdiction-balanced corpus with document-level train/dev/test splits.
2. Measure field-level span F1, critical-miss rate, provenance validity, calibration, comparison macro F1, change-impact recall, and reviewer-time reduction.
3. Compare the deterministic baseline, the current Legal-BERT-assisted alignment, n-grams, a fine-tuned legal-domain encoder, and constrained language-model systems.
4. Run blinded reviewer studies and report error taxonomies, confidence intervals, ablations, and cross-jurisdiction generalization.
5. Preserve the existing evidence contract so every learned result remains attributable and reviewable.
