# Closed-loop test statistical report

Test only; test workloads were not evaluated. Differences are Adaptive minus baseline, so negative values favor Adaptive.

| Baseline | Metric | Mean difference | 95% bootstrap CI | Wins–ties–losses | Holm p |
|---|---:|---:|---:|---:|---:|
| RMS | critical_misses | 0.1187 | [-0.4750, 0.7375] | 4–148–8 | 1 |
| RMS | total_misses | -0.4938 | [-1.7437, 0.8688] | 21–133–6 | 0.06696 |
| RMS | mean_response_ms | 0.6945 | [0.3335, 1.1082] | 35–67–58 | 0.03869 |
| RMS | context_switches | -2.7313 | [-6.1437, 0.1688] | 41–94–25 | 0.4081 |
| EDF | critical_misses | -1.7063 | [-4.0687, -0.0187] | 8–146–6 | 1 |
| EDF | total_misses | -3.6250 | [-8.7438, -0.5750] | 9–145–6 | 1 |
| EDF | mean_response_ms | -0.6374 | [-1.0918, -0.2552] | 14–140–6 | 0.4422 |
| EDF | context_switches | 8.2562 | [3.4062, 14.1875] | 0–141–19 | 0.0002119 |
| RMS+Boost | critical_misses | 0.1437 | [-0.4125, 0.7438] | 4–148–8 | 1 |
| RMS+Boost | total_misses | -0.4688 | [-1.7125, 0.8812] | 21–133–6 | 0.06696 |
| RMS+Boost | mean_response_ms | 0.6818 | [0.3215, 1.0952] | 37–67–56 | 0.0874 |
| RMS+Boost | context_switches | -3.9188 | [-7.3125, -0.9437] | 44–93–23 | 0.08562 |
| EDF+Boost | critical_misses | -1.1687 | [-2.5875, 0.0250] | 8–145–7 | 1 |
| EDF+Boost | total_misses | -3.5500 | [-8.4125, -0.6188] | 9–144–7 | 1 |
| EDF+Boost | mean_response_ms | -0.6620 | [-1.1444, -0.2612] | 18–136–6 | 0.1207 |
| EDF+Boost | context_switches | 3.8062 | [1.2125, 7.0250] | 7–137–16 | 0.4422 |

Wilcoxon signed-rank tests are two-sided. The bootstrap resamples complete task sets, preserving paired comparisons. Statistical significance does not replace practical-effect reporting.
