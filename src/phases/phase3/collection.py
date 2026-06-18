"""Phase 3 collection helpers."""

from __future__ import annotations

from .incident_build import build_incident_from_remote_run
from .remote_collection import merge_remote_run_outputs, run_remote_collection
from .remote_run import (
    build_input_from_remote_run,
    copy_remote_run_support_files,
    first_context,
    load_remote_executor_run_result,
    merge_remote_executor_result,
    merge_remote_executor_run_result,
    merge_remote_script_outputs,
    remote_executor_next_actions,
    remote_executor_required_user_action,
    script_run_dirs,
)
from .recollection import (
    DIRECTED_RECOLLECTION_CAP,
    collection_report_mentions_log_sink_gap,
    crashloop_logs_are_shallow,
    current_logs_are_short,
    details_has_items,
    directed_recollection_script_ids,
    evidence_mentions_dns_issue,
    filter_recollection_scripts_by_skill_pool,
    has_file_backed_log_sink,
    has_file_tail_logs,
    has_log_sink_record,
    incident_evidence_text,
    select_directed_recollection_script_ids,
    should_run_dns_recollection,
    should_run_log_file_tail_recollection,
    should_run_log_node_file_tail_recollection,
    should_run_log_sink_recollection,
    should_run_network_overlay_recollection,
    should_run_pod_describe_recollection,
    SCRIPT_DNS_COREDNS,
    SCRIPT_LOG_FILE_TAIL,
    SCRIPT_LOG_NODE_FILE_TAIL,
    SCRIPT_LOG_SINK_DISCOVER,
    SCRIPT_NETWORK_OVERLAY,
    SCRIPT_PODS_DESCRIBE,
    signal_bundle_has,
    signal_bundle_text,
    signal_object_pods,
    text_has_direct_error_terms,
)
from .recollection_run import run_directed_recollection_if_needed
from .report_gaps import (
    drop_closed_evidence_gaps,
    infer_gap_type,
    normalize_collection_report_gaps,
    record_recollection_skill_pool_miss,
)
from .scenario_routing import apply_scenario_routing_if_needed
from .skill_runtime import (
    enrich_skill_runtime_context,
    resolve_skill_runtime,
    write_skill_runtime_context,
)
