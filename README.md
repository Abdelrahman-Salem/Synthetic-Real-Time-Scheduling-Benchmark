# Synthetic Real Time Scheduling Benchmark

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22871510.svg)](https://doi.org/10.5281/zenodo.22871510)

Version 1.0.0

This repository contains a deterministic synthetic benchmark for evaluating
adaptive single processor real time schedulers that select among RMS, EDF,
RMS with bounded Priority Boost, and EDF with bounded Priority Boost. It
contains 640 task sets, frozen train validation test splits, state level
counterfactual labels, reference models, protocols, and frozen results.

## Authors

- Abdelrahman Mohamed Mohamed Salem, Faculty of Computers and Artificial
  Intelligence, Fayoum University, Egypt. Email: amm37@fayoum.edu.eg
- Ahmed Salama, Assoc. Professor, Department of Information Systems, Faculty
  of Computers and Artificial Intelligence, Fayoum University, Egypt.
- Mostafa Rabie, Assoc. Professor, Department of Computer Science, Faculty of
  Computers and Artificial Intelligence, Fayoum University, Egypt.

## Dataset

The benchmark is synthetic and simulation generated. It is not a trace of a
physical deployment. The generator uses master seed `20260920`. The suite
contains 320 training, 160 validation, and 160 held out test task sets. Each
task set has a 3000 ms horizon and combines task count, target utilization,
deadline, release, and execution demand profiles.

`data/workloads/manifest.json` is the authoritative index. Individual JSON
files contain explicit releases and execution demands. `data/states.jsonl`
contains 51,840 training and validation decision states and four
counterfactual policy outcomes per state. Test state labels were not generated
during model development.

## Benchmark tasks

1. Scheduler family selection between RMS and EDF.
2. Family specific selection between Base and bounded Priority Boost.
3. Closed loop policy selection at 100 ms decision intervals.

Primary metrics are critical deadline misses and total deadline misses.
Secondary metrics are completed job response time, context switches,
preemptions, Boost execution, and mode switches. Comparisons are paired by task
set. See the protocol files in the repository root.

## Frozen reference results

| Policy | Critical misses | Total misses | Mean response ms | Context switches |
|---|---:|---:|---:|---:|
| RMS | 115 | 661 | 11.631 | 50277 |
| EDF | 407 | 1162 | 12.837 | 48519 |
| RMS plus Boost | 111 | 657 | 11.639 | 50467 |
| EDF plus Boost | 321 | 1150 | 12.863 | 49231 |
| Adaptive | 134 | 582 | 12.290 | 49840 |

These are the once opened held out test results. Adaptive reduced total misses
numerically but did not establish a Holm corrected statistically significant
advantage at alpha 0.05. It also produced more critical misses than RMS and RMS
plus Boost. The results must not be used to retune the included models.

## Reproduction

Use Python 3.13 and install the pinned dependencies:

```bash
python -m pip install -r requirements.txt
```

Run the included test suite from `src`, then reproduce validation evaluation
with explicit paths:

```bash
cd src
python -m unittest discover -s . -p "test_*.py"
cd ..
```

```bash
cd src
python evaluate_closed_loop.py --workloads ../data/workloads --family-model ../models/family_model/without_current_mode.pkl --boost-model ../models/boost_model --out ../reproduction_validation
```

The final test outputs are already frozen under `results/final_test`. Do not
rerun or use them for model selection. SHA 256 checksums for every published
file are stored in `SHA256SUMS`.

## Citation and licenses

Use `CITATION.cff` for citation metadata. The archived version 1.0.0 dataset is
available at https://doi.org/10.5281/zenodo.22871510. Code is licensed under
MIT. Data and documentation are licensed under CC BY 4.0. See `LICENSE-CODE`
and `LICENSE-DATA`.
