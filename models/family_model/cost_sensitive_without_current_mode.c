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
        if (nominal_utilization_pct <= 94.875f) {
            if (mean_slack_ms <= 15.75f) {
                if (min_slack_ms <= 10f) {
                    if (execution_history_task_count <= 2.5f) {
                        return 1;  /* EDF */
                    } else {
                        return 1;  /* EDF */
                    }
                } else {
                    if (ready_queue_length <= 1.5f) {
                        return 0;  /* RMS */
                    } else {
                        return 0;  /* RMS */
                    }
                }
            } else {
                if (ready_queue_length <= 1.5f) {
                    if (mean_slack_ms <= 22.5f) {
                        return 0;  /* RMS */
                    } else {
                        return 1;  /* EDF */
                    }
                } else {
                    return 1;  /* EDF */
                }
            }
        } else {
            if (nominal_utilization_pct <= 95.2083359f) {
                if (mean_slack_ms <= 8.5f) {
                    if (completed_execution_range_pct <= 34.66259f) {
                        return 1;  /* EDF */
                    } else {
                        return 0;  /* RMS */
                    }
                } else {
                    if (min_critical_slack_ms <= 36f) {
                        return 0;  /* RMS */
                    } else {
                        return 0;  /* RMS */
                    }
                }
            } else {
                if (min_slack_ms <= 7.5f) {
                    if (critical_ready_count <= 0.5f) {
                        return 1;  /* EDF */
                    } else {
                        return 0;  /* RMS */
                    }
                } else {
                    if (execution_history_task_count <= 4.5f) {
                        return 1;  /* EDF */
                    } else {
                        return 1;  /* EDF */
                    }
                }
            }
        }
    } else {
        if (mean_slack_ms <= 55.4500008f) {
            if (completed_execution_range_pct <= 4f) {
                if (min_slack_ms <= 26.5f) {
                    if (misses_last_100ms <= 0.5f) {
                        return 0;  /* RMS */
                    } else {
                        return 0;  /* RMS */
                    }
                } else {
                    if (mean_slack_ms <= 44.125f) {
                        return 1;  /* EDF */
                    } else {
                        return 0;  /* RMS */
                    }
                }
            } else {
                if (mean_slack_ms <= 21.583333f) {
                    if (ready_queue_length <= 0.5f) {
                        return 1;  /* EDF */
                    } else {
                        return 0;  /* RMS */
                    }
                } else {
                    if (nominal_utilization_pct <= 110.083332f) {
                        return 1;  /* EDF */
                    } else {
                        return 0;  /* RMS */
                    }
                }
            }
        } else {
            if (task_count <= 6.5f) {
                if (task_count <= 4f) {
                    return 1;  /* EDF */
                } else {
                    if (min_slack_ms <= 46f) {
                        return 0;  /* RMS */
                    } else {
                        return 0;  /* RMS */
                    }
                }
            } else {
                if (execution_history_task_count <= 9.5f) {
                    if (mean_slack_ms <= 59.9285717f) {
                        return 1;  /* EDF */
                    } else {
                        return 1;  /* EDF */
                    }
                } else {
                    if (ready_queue_length <= 3.5f) {
                        return 0;  /* RMS */
                    } else {
                        return 1;  /* EDF */
                    }
                }
            }
        }
    }
}
