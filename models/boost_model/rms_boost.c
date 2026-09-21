#include <stdint.h>

/* RMS: 0=BASE, 1=BOOST. */
uint8_t decide_rms_boost(
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
    if (nominal_utilization_pct <= 79.7916679f) {
        return 0;  /* BASE */
    } else {
        if (completed_execution_range_pct <= 26.2865486f) {
            return 1;  /* BOOST */
        } else {
            return 0;  /* BASE */
        }
    }
}
