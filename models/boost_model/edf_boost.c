#include <stdint.h>

/* EDF: 0=BASE, 1=BOOST. */
uint8_t decide_edf_boost(
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
    if (misses_last_100ms <= 0.5f) {
        if (min_slack_ms <= -0.5f) {
            if (nominal_utilization_pct <= 110.041668f) {
                return 0;  /* BASE */
            } else {
                return 1;  /* BOOST */
            }
        } else {
            if (nominal_utilization_pct <= 102.5f) {
                if (nominal_utilization_pct <= 94.9583321f) {
                    return 0;  /* BASE */
                } else {
                    if (nominal_utilization_pct <= 95.0416679f) {
                        return 0;  /* BASE */
                    } else {
                        return 0;  /* BASE */
                    }
                }
            } else {
                if (completed_execution_range_pct <= 5.55555534f) {
                    if (min_slack_ms <= 19.5f) {
                        return 1;  /* BOOST */
                    } else {
                        return 0;  /* BASE */
                    }
                } else {
                    return 0;  /* BASE */
                }
            }
        }
    } else {
        if (nominal_utilization_pct <= 102.416668f) {
            if (completed_execution_range_pct <= 37.5436745f) {
                return 0;  /* BASE */
            } else {
                return 0;  /* BASE */
            }
        } else {
            if (completed_execution_range_pct <= 5.55555534f) {
                if (mean_slack_ms <= 52.75f) {
                    if (nominal_utilization_pct <= 110.625f) {
                        return 1;  /* BOOST */
                    } else {
                        return 1;  /* BOOST */
                    }
                } else {
                    if (min_slack_ms <= 39.0f) {
                        return 0;  /* BASE */
                    } else {
                        return 1;  /* BOOST */
                    }
                }
            } else {
                if (min_slack_ms <= -6.5f) {
                    return 0;  /* BASE */
                } else {
                    return 0;  /* BASE */
                }
            }
        }
    }
}
