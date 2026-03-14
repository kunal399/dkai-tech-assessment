## Task 2: ML Basics & Optimization

**Goal:** Build and improve a baseline ML model on a real dataset.

**Tech Stack:** Python, PySpark MLlib, Google Colab

**Dataset:** Titanic (891 rows, 38.4% survival rate)

**Baseline Model:** Random Forest Classifier

### How to Run

Open `task2/task2.ipynb` in Google Colab and run all cells.

> Note: PySpark is installed inside the notebook automatically. No local setup needed.

### Improvements Applied
1. **Feature Engineering** — Added Title, family_size, is_alone, fare_per_person, age_class
2. **Hyperparameter Tuning** — Grid search over numTrees, maxDepth, minInstancesPerNode using 3-fold CV

### Results Summary

| Model | CV AUC-ROC | Train Accuracy | Train F1 |
|---|---|---|---|
| Baseline RF | 0.8688 | 0.8507 | 0.8475 |
| + Feature Engineering | 0.8720 | 0.8519 | 0.8492 |
| + Tuned Params | 0.8724 | 0.8631 | 0.8609 |

See `task2/writeup.md` for the full comparison write-up.

---

## Requirements

- Python 3.8+
- pip
- Google Colab (for Task 2)
