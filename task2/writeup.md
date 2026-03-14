# Task 2: ML Basics & Optimization — Model Comparison Write-Up

**Dataset:** Titanic (891 rows, 38.4% survival rate)  
**Framework:** PySpark MLlib  
**Baseline Model:** Random Forest Classifier  

---

## Evaluation Strategy

5-fold cross-validation on the full dataset (713 train / 178 test per fold), using AUC-ROC as the primary metric.  
A single 80/20 split was avoided because with only 891 rows, 3 wrong predictions cause ~2% accuracy swings, making single-split scores unstable and unreliable.

---

## Baseline Model — Random Forest (100 trees, depth=5)

| Metric | Score |
|---|---|
| CV AUC-ROC (5-fold) | 0.8688 |
| Train Accuracy | 0.8507 |
| Train F1 | 0.8475 |

A standard Random Forest with default features: Pclass, Sex, Age, SibSp, Parch, Fare, Embarked.

---

## Improvement 1 — Feature Engineering (+0.0032 AUC)

| Metric | Baseline | After FE | Δ |
|---|---|---|---|
| CV AUC-ROC | 0.8688 | 0.8720 | +0.0032 |
| Train Accuracy | 0.8507 | 0.8519 | +0.0012 |
| Train F1 | 0.8475 | 0.8492 | +0.0017 |

Five new features were added:
- **Title** — extracted from passenger name (Mr, Mrs, Miss, Master, Rare). Encodes gender, age group, and social status in a single variable — all strong survival predictors.
- **family_size** — SibSp + Parch + 1
- **is_alone** — binary flag, 1 if travelling alone
- **fare_per_person** — Fare ÷ family_size
- **age_class** — Age × Pclass (interaction term)

The Title feature was the most impactful as it captures social hierarchy and demographic information that raw name strings cannot provide to the model directly.

---

## Improvement 2 — Hyperparameter Tuning (+0.0037 AUC)

| Metric | Baseline | After Tuning | Δ |
|---|---|---|---|
| CV AUC-ROC | 0.8688 | 0.8724 | +0.0037 |
| Train Accuracy | 0.8507 | 0.8631 | +0.0124 |
| Train F1 | 0.8475 | 0.8609 | +0.0134 |

A constrained grid search tested 18 combinations across:
- **numTrees:** 100, 200
- **maxDepth:** 3, 4, 5
- **minInstancesPerNode:** 2, 5, 10

Using 3-fold CV with AUC-ROC as the selection metric.

**Best parameters found: 200 trees, depth=5, minInstancesPerNode=2**

Train accuracy improved by +1.24% and Train F1 by +1.34%, showing the tuned model fits the training data better. The CV AUC gain of +0.0037 confirms it also generalizes slightly better than the baseline.

---

## Final Results Summary

| Model | CV AUC-ROC | Train Accuracy | Train F1 |
|---|---|---|---|
| Baseline RF | 0.8688 | 0.8507 | 0.8475 |
| + Feature Engineering | 0.8720 | 0.8519 | 0.8492 |
| + Tuned Params | 0.8724 | 0.8631 | 0.8609 |

---

## Key Takeaway

Both improvements helped, but neither dramatically so — expected on a small 891-row dataset. Feature engineering gave the bigger generalization gain in CV AUC (+0.0032), while hyperparameter tuning improved train-set fitting more noticeably (+0.0124 accuracy). Combined, the final model achieved **CV AUC of 0.8724 vs baseline 0.8688**, a net gain of **+0.0037**.
