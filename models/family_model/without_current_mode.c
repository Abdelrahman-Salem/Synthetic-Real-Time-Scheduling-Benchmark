#include <stdint.h>

/* 0=RMS family, 1=EDF family. Pilot model only. */
uint8_t decide_scheduler_family(
    float nominal_utilization_pct,
    float task_count,
    float ready_queue_length,
    float critical_ready_count,
    float min_slack_ms,
    float mean_slack_ms,
    float min_critical_slack_ms,
    float misses_last_100ms,
    float critical_misses_last_100ms,
    float completed_execution_range_pct,
    float execution_history_task_count,
    float boost_window_remaining_ms,
    float boost_window_phase_ms,
    float critical_job_boost_budget_remaining_ms,
    float wcet_exhausted_active_count
) {
    if (nominal_utilization_pct <= 108.875f) {
        if (critical_misses_last_100ms <= 0.5f) {
            if (task_count <= 6.5f) {
                if (nominal_utilization_pct <= 94.5833321f) {
                    if (nominal_utilization_pct <= 80.875f) {
                        return 1;  /* EDF */
                    } else {
                        return 1;  /* EDF */
                    }
                } else {
                    if (completed_execution_range_pct <= 37.4094772f) {
                        return 1;  /* EDF */
                    } else {
                        return 0;  /* RMS */
                    }
                }
            } else {
                return 1;  /* EDF */
            }
        } else {
            if (nominal_utilization_pct <= 95.0416679f) {
                if (ready_queue_length <= 1.5f) {
                    return 1;  /* EDF */
                } else {
                    return 1;  /* EDF */
                }
            } else {
                if (misses_last_100ms <= 1.5f) {
                    if (min_slack_ms <= 11f) {
                        return 0;  /* RMS */
                    } else {
                        return 1;  /* EDF */
                    }
                } else {
                    if (mean_slack_ms <= 26.75f) {
                        return 0;  /* RMS */
                    } else {
                        return 0;  /* RMS */
                    }
                }
            }
        }
    } else {
        if (misses_last_100ms <= 0.5f) {
            if (mean_slack_ms <= 38.7875004f) {
                if (completed_execution_range_pct <= 23.9592495f) {
                    if (nominal_utilization_pct <= 109.25f) {
                        return 1;  /* EDF */
                    } else {
                        return 0;  /* RMS */
                    }
                } else {
                    if (min_slack_ms <= -6.5f) {
                        return 0;  /* RMS */
                    } else {
                        return 1;  /* EDF */
                    }
                }
            } else {
                if (execution_history_task_count <= 2.5f) {
                    if (mean_slack_ms <= 52.8374996f) {
                        return 0;  /* RMS */
                    } else {
                        return 1;  /* EDF */
                    }
                } else {
                    if (ready_queue_length <= 7.5f) {
                        return 1;  /* EDF */
                    } else {
                        return 1;  /* EDF */
                    }
                }
            }
        } else {
            if (min_slack_ms <= 23.5f) {
                if (completed_execution_range_pct <= 13.1386719f) {
                    if (mean_slack_ms <= 56.7999992f) {
                        return 0;  /* RMS */
                    } else {
                        return 1;  /* EDF */
                    }
                } else {
                    if (min_critical_slack_ms <= 12.5f) {
                        return 1;  /* EDF */
                    } else {
                        return 0;  /* RMS */
                    }
                }
            } else {
                if (min_critical_slack_ms <= 55f) {
                    if (critical_misses_last_100ms <= 0.5f) {
                        return 0;  /* RMS */
                    } else {
                        return 1;  /* EDF */
                    }
                } else {
                    if (task_count <= 9f) {
                        return 1;  /* EDF */
                    } else {
                        return 1;  /* EDF */
                    }
                }
            }
        }
    }
}
