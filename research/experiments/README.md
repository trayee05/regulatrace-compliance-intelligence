# External deontic-modality proxy experiment

This experiment evaluates **provision-level, five-class modality classification** on the public dataset accompanying Minkova, Chakravarthy, and van Dijck (NLLP 2023), DOI [10.34894/HQ8LIH](https://doi.org/10.34894/HQ8LIH). The dataset is licensed CC BY 4.0 by its authors. The script downloads the released `original_df.csv` from DataverseNL and checks its SHA-256 before use; the dataset is not copied into this repository.

Run from the repository root with Python 3.12 after installing the pinned experiment dependencies into `.venv`:

```sh
.venv/bin/python -m pip install -r research/experiments/requirements.txt
.venv/bin/python -m research.experiments.deontic_proxy
```

The protocol selects only annotator A1's 567 rows, strips surrounding whitespace, removes one same-label duplicate, and excludes the separate unannotated `None` rows. The resulting set has 566 examples. It compares a majority predictor, the existing RegulaTrace rule engine, word TF-IDF with logistic regression, word TF-IDF with linear SVM, and character TF-IDF with linear SVM. Fixed hyperparameters are in the script. Three stratified grouped folds use seed 42; texts with character n-gram cosine similarity at least 0.75 are kept in one fold. TF-IDF vectors for the trained models are fit inside each training fold.

The reported accuracy and macro F1 are fold means with one fold standard deviation. The confusion matrix uses pooled out-of-fold predictions. `Power` and `Right` are not output classes of the RegulaTrace engine; its `INFORMATION` or `RECOMMENDATION` result is counted as an abstention and as an error against the five gold labels. This is a **classification proxy**, not a measure of obligation-span extraction, actor/action fields, source-offset quality, policy comparison, or real-world compliance.

The released CSV lacks source-document identifiers, so similarity grouping cannot guarantee source-disjoint evaluation. The rare `Power`, `Right`, and `Prohibition` classes also make the per-class estimates unstable. Do not compare these numbers directly to the original paper's reported results, which used different data processing and splits.

## Regulatory versus constitutive statements

The second experiment uses the human-labeled `complete_training_data.csv` from Moodley, Brandsma, Blom-Hansen, and Meijer's [EU rules reproducibility release](https://doi.org/10.5281/zenodo.8200001). The script downloads and SHA-256 checks the file. It normalizes whitespace, removes repeated sentence text, and excludes 269 exact-text groups with discordant binary labels. This leaves 5,831 distinct sentences from 379 CELEX acts: 2,494 regulatory and 3,337 constitutive. The source files are not copied into this repository.

```sh
.venv/bin/python -m research.experiments.regulatory_binary
```

Three stratified folds are grouped by CELEX act (seed 42); the vectorizer is fitted only on each training fold. Baselines are the majority class, RegulaTrace's any-normative-record decision, word TF-IDF with logistic regression, word TF-IDF with linear SVM, and character TF-IDF with linear SVM. The positive class is `regulatory`. Accuracy and positive-class F1 are means across folds with one fold standard deviation; precision, recall, and confusion matrices come from pooled out-of-fold predictions.

This is a **sentence classification task**, not exact obligation-span detection. The authors' `regulatory` label requires a legal obligation for an agent; mapping any RegulaTrace normative output to that label is a deliberately broad baseline. Nearly all retained sentences contain `shall`, so the experiment probes whether lexical modal cues alone separate regulatory from constitutive statements. Excluding discordant texts and using the source's labels affects the sample; no legal adjudication or correction of the source labels was performed.
