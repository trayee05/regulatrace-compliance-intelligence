# RegulaTrace research presentation — speaker notes

**Length:** 10 minutes, including a two-minute live demo. These notes map a proposed slide order to the current paper figures and application; they are not a slide deck. Use the current [LaTeX source](../paper/regulatrace-preprint/main.tex) and its editor preview for the manuscript. The PDF in `output/pdf/` is an earlier export and does not contain the external experiment results.

## Run of show

| Time | Slide / screen | Visual |
| --- | --- | --- |
| 0:00–0:35 | 1. Title and hook | RegulaTrace title; one sourced obligation record |
| 0:35–1:30 | 2. The research problem | Text → duty → evidence span |
| 1:30–2:25 | 3. What the system does | App workflow / evidence graph |
| 2:25–3:25 | 4. Evaluation design | Two datasets, grouped folds, metrics |
| 3:25–4:25 | 5. Deontic modality result | [Five-class score plot](../paper/regulatrace-preprint/figures/deontic_proxy_scores.png) |
| 4:25–5:35 | 6. Regulatory-function result | [Binary score plot](../paper/regulatrace-preprint/figures/regulatory_binary_scores.png) |
| 5:35–6:35 | 7. What went wrong | [Binary confusion plots](../paper/regulatrace-preprint/figures/regulatory_binary_confusion.png) |
| 6:35–8:35 | 8. Live demo | Local app: Executive Brief → Obligation Lab → correction → Evidence Graph |
| 8:35–9:30 | 9. Limits and next experiment | [Per-class F1 plot](../paper/regulatrace-preprint/figures/deontic_proxy_per_class.png) |
| 9:30–10:00 | 10. Takeaway | Three claims, one open question |

## Slide-by-slide talk track

### 1. Title and hook (0:00–0:35)

**Say:** “RegulaTrace studies a narrow but important problem: can we turn regulatory language into a duty record that a reviewer can trace back to the exact text? A plausible-looking paraphrase is not enough if we cannot locate the source or if we miss who must act.”

**Transition:** “That gives us two separate questions: is the language classified correctly, and is the extracted record actually reviewable?”

### 2. The research problem (0:35–1:30)

**Show:** A short fictional example: “The provider must retain logs and notify the authority within 24 hours.” Highlight that this contains two acts but the current engine stores one action field.

**Say:** “The system records modality, actor, action, timing, conditions, exceptions, and an exact Unicode source interval. The interval lets us check what text generated a record. It does not prove that the action and exceptions were interpreted correctly. In this example the evidence span is valid, but the one-record-per-clause design merges two responsibilities.”

### 3. What the system does (1:30–2:25)

**Show:** The local app or a screenshot of Obligation Lab and Evidence Graph.

**Say:** “This is an implemented deterministic baseline. It ingests text-based PDF, DOCX, TXT, and Markdown; segments clauses; applies ordered modal-cue rules; extracts heuristic fields; and stores reviewer corrections with before-and-after audit entries. Policy comparison and version change are review signals. The numerical confidence is a heuristic, not a calibrated probability.”

**Transition:** “We then asked whether the rules hold up outside our own examples.”

### 4. Evaluation design (2:25–3:25)

**Show:** Two dataset cards; keep the task names distinct.

**Say:** “The 16-case built-in suite is only a development smoke test. For measured comparisons, we used two independently released EU datasets. The first has 566 distinct, five-class deontic examples from one annotator; because it lacks document IDs, we grouped highly similar texts across three folds. The second has 5,831 distinct regulatory-or-constitutive sentences from 379 CELEX acts; all sentences from an act stay in one fold. We compare the existing rules with majority class, word TF-IDF logistic regression, and word and character TF-IDF SVMs. Reported bars are fold means; whiskers are one fold standard deviation, not confidence intervals.”

**Important wording:** These are **sentence-classification proxy tasks**. Neither dataset labels the full obligation span or every actor/action field.

### 5. Deontic modality result (3:25–4:25)

**Show:** `deontic_proxy_scores.png`.

**Say:** “On the five-class proxy, RegulaTrace rules reach 92.2% accuracy and 0.543 macro F1. The best learned macro F1 among these fixed baselines is 0.499 from word TF-IDF logistic regression. The high accuracy needs context: 444 of 566 examples are obligations. A majority predictor already gets 78.4% accuracy but only 0.176 macro F1. Our rules recognize explicit obligation, permission, and prohibition cues, yet have no output classes for power or right.”

**Transition:** “That looks encouraging until we change the question.”

### 6. Regulatory-function result (4:25–5:35)

**Show:** `regulatory_binary_scores.png`.

**Say:** “In the second dataset, the question is whether a sentence imposes a regulatory obligation on an agent or is constitutive. Almost every retained sentence contains ‘shall,’ so detecting that word is not enough. Here the same RegulaTrace rules fall to 41.9% mean accuracy and 0.588 regulatory-class F1. A word TF-IDF linear SVM reaches 85.2% accuracy and 0.810 regulatory F1. The difference is not a cross-dataset ranking; it exposes how much the task definition changes what counts as success.”

### 7. What went wrong (5:35–6:35)

**Show:** `regulatory_binary_confusion.png`.

**Say:** “The rule baseline finds all 2,494 labeled regulatory sentences, but falsely flags 3,336 of 3,337 constitutive sentences. Its positive recall is 100%, yet its precision is only 42.8%. The SVM cuts false positives to 298, but misses 570 regulatory sentences. We should discuss both sides of that trade-off rather than celebrate one accuracy number. A commencement provision that says a decision ‘shall enter into force’ illustrates why a modal cue does not automatically mean an actionable duty for our target actor.”

### 8. Live demo (6:35–8:35)

**Before presenting:** Run `sh ./start-regulatrace.sh` from the repository root and confirm `http://127.0.0.1:8000/#executive` loads. Keep the fictional `examples/RegulaTrace_Demo_Regulation.docx` available as a backup input. The example's authority and jurisdiction are fictional.

1. **Executive Brief** (`#executive`, ~20 seconds): Select **Run the live story**. Say: “This runs the local application, not a scripted screenshot.”
2. **Obligation Lab** (`#obligation-lab`, ~45 seconds): Open an extracted record. Point to its evidence clause, source ID, and offsets. Say: “These offsets recover text in the supplied or extracted document; they are not official PDF page coordinates.”
3. **Correction and audit** (~35 seconds): Correct one visible field, save, reopen the case, and show the before/after audit entry. Say: “A human correction stays visible alongside the original evidence.”
4. **Evidence Graph** (`#evidence-graph`, ~20 seconds): Show the source-to-record-to-review chain. Say: “The graph makes provenance inspectable; it does not certify legal correctness.”

**If time remains:** Open Policy Comparator (`#comparator`) or Change Radar (`#change-radar`) and describe its output as a triage signal. The Evaluation page (`#evaluation`) runs the 16-case synthetic suite; it is not the external cross-validation experiment.

### 9. Limits and next experiment (8:35–9:30)

**Show:** `deontic_proxy_per_class.png`.

**Say:** “The per-class plot exposes a blind spot: the rule engine has zero F1 for power and right because it cannot emit those classes. The external datasets do not annotate obligation spans, linked exceptions, or field-level source evidence. The next experiment is a source-disjoint, independently annotated document set with span and field labels, then a blinded reviewer comparison. Until then, our measured claims are about these classification tasks and our software checks.”

### 10. Takeaway (9:30–10:00)

**Say:** “Three takeaways. First, provenance should be part of the output contract. Second, explicit cue recognition can score well on deontic labels and still fail to distinguish a regulatory duty from constitutive text. Third, the next serious claim requires end-to-end annotations and reviewer outcomes. RegulaTrace gives us a reproducible baseline and a clear failure to improve.”

## Numbers to keep straight

| Measure | Value | Meaning |
| --- | ---: | --- |
| Deontic sample | 566 texts, 551 similarity groups | One annotator; five classes; no act IDs |
| Deontic rules | 92.2% accuracy; 0.543 macro F1 | Three-fold mean; not end-to-end extraction |
| Deontic word logistic regression | 86.6% accuracy; 0.499 macro F1 | Best learned macro F1 among tested models |
| Binary sample | 5,831 sentences, 379 CELEX acts | 2,494 regulatory; 3,337 constitutive |
| Binary rules | 41.9% accuracy; 0.588 regulatory F1 | Three-fold mean; very high false-positive rate |
| Binary word SVM | 85.2% accuracy; 0.810 regulatory F1 | Best tested binary classifier |
| Rule binary confusion | 2,494 TP; 3,336 FP; 0 FN; 1 TN | Pooled out-of-fold counts |
| SVM binary confusion | 1,924 TP; 298 FP; 570 FN; 3,039 TN | Pooled out-of-fold counts |
| Built-in challenge suite | 16/16 synthetic cases | Development check only |

The binary pooled accuracy for the rules is 42.8%, while the table and talk use the **unweighted mean of three uneven fold accuracies, 41.9%**. Both are correct but answer slightly different aggregation questions.

## Likely questions

**“Why not just report the 92.2%?”** It is provision-level modality classification on an imbalanced, preprocessed dataset. The 0.543 macro F1 and zero score on power/right show what accuracy hides. The second task tests a different legal-function distinction and reveals extreme false positives.

**“Did you evaluate obligation extraction?”** We evaluated two external sentence-level proxy tasks and a synthetic software suite. The span-and-field evaluator is implemented, but there is no independently annotated end-to-end obligation-record test set yet.

**“Why no transformer result?”** We established transparent majority, logistic-regression, and SVM baselines first. A general and legal-domain encoder comparison belongs on a common, frozen split with the same output contract; none has been run for this draft.

**“Does this certify compliance?”** No. Source offsets verify only that evidence text can be recovered from the supplied input. Legal interpretation, source authority, and compliance decisions remain with qualified reviewers.

**“Can we compare these scores with the source papers?”** No direct comparison: dataset filtering, label mappings, folds, and model setup differ. The scripts and JSON record the exact protocol used here.

## Source files for last-minute checks

- Current manuscript: [`paper/regulatrace-preprint/main.tex`](../paper/regulatrace-preprint/main.tex)
- Experiment methods and reproduction: [`research/experiments/README.md`](../research/experiments/README.md)
- Exact deontic fold results: [`deontic_proxy_results.json`](../research/experiments/results/deontic_proxy_results.json)
- Exact binary fold results: [`regulatory_binary_results.json`](../research/experiments/results/regulatory_binary_results.json)
- End-to-end annotation design: [`research/PROTOCOL.md`](../research/PROTOCOL.md)
