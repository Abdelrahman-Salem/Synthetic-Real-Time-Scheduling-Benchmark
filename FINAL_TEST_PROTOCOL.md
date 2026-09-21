# Frozen final-test protocol

The family model, both Boost selectors, feature set, decision interval (100 ms),
Boost limits, workload generator, metrics, and statistical procedure were fixed
using training and validation only. `evaluate_final_test.py` loads the held-out
test split once, without fitting, selecting, or modifying any model parameter.

The output directory name is intentionally conspicuous and execution refuses to
overwrite it. Provenance records SHA-256 hashes of the workload manifest and all
three model files. After this run, the test results are final. Any subsequent
method change requires a new independently generated test split and must not be
reported as evaluation on the original untouched test set.
