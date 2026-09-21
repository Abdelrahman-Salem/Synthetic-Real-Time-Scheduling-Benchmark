# Validation statistical protocol

Each workload is a paired experimental unit because all schedulers receive the
same releases and execution demands. Adaptive-minus-baseline differences are
reported for each metric. A deterministic 10,000-resample task-set bootstrap
estimates 95% confidence intervals for the paired mean difference. Two-sided
Wilcoxon signed-rank tests use the Pratt treatment of zero differences. Holm's
method controls family-wise error across the 16 reported comparisons.

Critical deadline misses and total deadline misses are the predeclared primary
metrics. Response time and context switches are secondary. Results include
effect sizes (paired differences and win/tie/loss counts), not p-values alone.
Only validation workloads are analyzed; the held-out test split remains sealed.
