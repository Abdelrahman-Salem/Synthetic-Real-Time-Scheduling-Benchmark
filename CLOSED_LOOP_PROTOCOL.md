# Closed-loop validation protocol

The deployable selector is evaluated every 100 ms. At each decision boundary,
features are computed after releases and before dispatch. The family tree first
selects RMS or EDF; the corresponding family-specific tree then selects BASE or
Boost. That policy controls the next interval and therefore changes future state.

All methods receive the same stored validation workloads and exact execution
demands. Baselines are static RMS, EDF, RMS+Boost, and EDF+Boost. Inference and
switching overhead are assumed zero in this simulation and must be measured on
hardware later. Test workloads are neither loaded nor evaluated.

Primary comparison is lexicographic: critical deadline misses first, followed by
total deadline misses. Secondary measures are completed-job response time,
context switches, preemptions, Boost execution, and adaptive mode switches.
