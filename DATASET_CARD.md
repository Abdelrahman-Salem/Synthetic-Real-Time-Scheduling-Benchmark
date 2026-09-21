# Dataset Card

## Purpose

The dataset supports reproducible research on adaptive selection among RMS,
EDF, and bounded critical task Priority Boost variants in a preemptive single
processor simulator.

## Composition

- 640 task sets: 320 train, 160 validation, and 160 test.
- Task counts: 3, 5, 8, and 10.
- Target utilization: 0.40, 0.60, 0.80, 0.95, and 1.10.
- Deadlines: implicit or constrained.
- Releases: synchronous, fixed offsets, jitter, or bursts.
- Execution demand: fixed WCET or deterministic variable demand between 50 and
  100 percent of WCET.
- At least 25 percent of tasks in each set are marked critical.
- Horizon: 3000 ms; simulation resolution: 1 ms.

## Creation and splits

All cases were produced by the bundled deterministic generator from master seed
20260920. Split identity is encoded before sampling. Explicit releases and
demands are stored so every scheduler receives identical exogenous input. The
test split was sealed during training and validation and opened once for final
evaluation.

## Labels

At 100 ms checkpoints with a full 400 ms lookahead, each of four policies was
replayed from the same simulator snapshot. Outcomes prioritize critical misses
then total misses lexicographically. Many states have tied optimal policies;
ties are retained and documented rather than randomly forced into one class.

## Limitations

This is synthetic simulation data, not hardware timing data. The simulator
assumes a single CPU, 1 ms ticks, zero scheduling and inference overhead, and
deadline no greater than period. Workload distributions are designed, not
empirically fitted to an industrial domain. Results therefore demonstrate
behavior under this benchmark and should not be generalized directly to an
ATmega32 or safety critical deployment without hardware measurements.

## Ethical and privacy considerations

The dataset contains no human subjects, personal data, telemetry, or private
production traces. The main risks are methodological: test set reuse, selective
reporting, and overstating simulated results. Frozen splits, checksums, and
complete negative as well as positive results are provided to reduce these
risks.

## Maintenance

Version 1.0.0 is immutable. Corrections must be released as a new version with
a documented changelog. New model development should create a new held out test
split rather than tune against the published test results.

