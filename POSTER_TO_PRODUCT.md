# Poster to product: a defensible presentation story

## What runs today

| Poster concept | Live RegulaTrace implementation | What to show |
| --- | --- | --- |
| Legal clause input | Paired clauses with citations, URLs, effective dates, and scenario controls | Load either Contradiction Lab example |
| Deontic entity extraction | Typed actor, action, modality, record, scope, duration, exception, and evidence | Inspect the two tuple cards |
| Knowledge graph grounding | Explicit `IS_A`/`SAME_AS` facts, graph nodes and edges, optional Neo4j persistence | Remove one fact and see an indeterminate result |
| Symbolic verification | Z3 compiles applicable erase/retain constraints for one scenario | Read the two constraints and `check-sat` trace |
| Compliance verdict | SAT, UNSAT, or indeterminate with an unsat core and JSON export | Run the synthetic deadlock, then the official example |
| Indian legal encoder | The published InLegalBERT checkpoint supplies advisory embedding similarity when installed | Point to the active model stage and cosine, then to explicit graph facts |
| API | FastAPI, Pydantic, OpenAPI, structured errors | Open `/api/docs` |
| Evaluation | 28 backend tests, 7 JavaScript tests, existing 16-case obligation challenge suite | Run `pytest` and `npm test` or show Evaluation Console |

The poster also names **DSPy** and **Ragas**. Optional adapters exist: DSPy can produce review candidates when an LM endpoint is configured, and the source-scoring API can run Ragas' ID-based context precision against supplied reference labels. They are shown as *not configured* in the default proof because no LM or reference labels are provided. No language-model extractor, Ragas score, or fine-tuned NER claim is fabricated. The current typed extractor is a reproducible pattern baseline. A paper can compare it with those systems after a versioned, annotated Indian-law dataset exists.

## A three-minute demo

1. Open `http://127.0.0.1:8000/#contradiction-lab` and select **Provable synthetic deadlock**. State that these are teaching rules, not Indian statutes.
2. Run Z3. Both rules bind the same actor and records after closure. The solver receives `O(Erase(x))` and `F(Erase(x))`; it returns UNSAT and cites `DEMO-ERASE` and `DEMO-KEEP` in the core.
3. Load **DPDP + RBI KYC**. Show the actor and record `IS_A` graph facts, effective date, five-year retention duty, and DPDP legal-retention exception. Run Z3. The result is SAT because the erasure rule is excepted in this modeled situation.
4. Remove `Example Bank | IS_A | Data Fiduciary` from the graph facts and rerun. The app returns **INDETERMINATE** instead of guessing that the bank has the statutory role.
5. Export proof JSON. It includes source links, tuple evidence, statuses, graph, constraints, unsat core, model stages, and assumptions.

## Why the official example is more interesting than the poster's shortcut

The [DPDP Act section 8(7)](https://www.indiacode.nic.in/bitstream/123456789/22037/2/a2023-22.pdf) includes a legal-retention exception, and section 12(3) preserves retention necessary for compliance with law. [RBI KYC paragraph 46](https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=11566) requires preservation of customer identification records for at least five years after the business relationship ends. The [commencement notification](https://egazette.gov.in/WriteReadData/2025/267647.pdf) stages the relevant DPDP provisions for 18 months after 13 November 2025. A system that compares only similar wording could falsely claim a legal deadlock. RegulaTrace exposes the conditions that decide whether a contradiction can actually be proved.

## Honest research claim

This release demonstrates **scoped, source-linked constraint checking** for a limited erase/retain fragment. It does not prove compliance with Indian law. A future study should collect expert-labeled regulatory pairs, annotate actor/entity equivalence, effective dates, exceptions, and contradiction verdicts, then report field F1, logic precision/recall, false-deadlock rate, calibration, and ablations for graph facts, InLegalBERT, and a configured DSPy extraction system. A Ragas evaluation would need a defined retrieval/generation task and a reference dataset.
