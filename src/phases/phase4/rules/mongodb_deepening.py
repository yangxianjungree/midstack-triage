"""MongoDB evidence-deepening checks for Phase 4 rules."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Set, Tuple


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> Any:
    if isinstance(value, dict) and "low" in value:
        return value.get("low")
    return value


def _member_names(record: Dict[str, Any]) -> Set[str]:
    names = set()
    for member in record.get("members") or []:
        if isinstance(member, dict) and member.get("name"):
            names.add(str(member["name"]))
    return names


def _self_config(record: Dict[str, Any]) -> Tuple[Any, Any]:
    self_member = record.get("self_member") or {}
    return (
        _number(self_member.get("config_version")),
        _number(self_member.get("config_term")),
    )


def _group_by_replica_set(member_records: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for record in member_records:
        replica_set_id = _text(record.get("replica_set_id"))
        if not replica_set_id:
            continue
        groups.setdefault(replica_set_id, []).append(record)
    return groups


def _finding(
    finding_id: str,
    statement: str,
    evidence_refs: List[str],
    supports: List[str],
    refutes: List[str],
    severity: str,
) -> Dict[str, Any]:
    return {
        "finding_id": finding_id,
        "statement": statement,
        "evidence_refs": evidence_refs,
        "supports": supports,
        "refutes": refutes,
        "severity": severity,
    }


def replica_set_invariant_findings(member_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for replica_set_id, records in _group_by_replica_set(member_records).items():
        if len(records) < 2:
            continue
        evidence_refs = ["structured_record.details.replica_members:%s" % _text(item.get("source_pod_ref")) for item in records]

        config_views = {_self_config(item) for item in records}
        if len(config_views) > 1:
            detail = ", ".join(
                "%s config_version=%s config_term=%s"
                % (_text(item.get("source_pod_ref")), _self_config(item)[0], _self_config(item)[1])
                for item in records
            )
            findings.append(
                _finding(
                    "mongodb.replica_set.config_divergence",
                    "Replica set %s has divergent self config_version/config_term views: %s."
                    % (replica_set_id, detail),
                    evidence_refs,
                    ["replica_set_config_divergence", "split_brain_enabling_condition"],
                    [],
                    "high",
                )
            )

        membership_views = {tuple(sorted(_member_names(item))) for item in records}
        if len(membership_views) > 1:
            detail = ", ".join(
                "%s members=%s" % (_text(item.get("source_pod_ref")), sorted(_member_names(item)))
                for item in records
            )
            findings.append(
                _finding(
                    "mongodb.replica_set.membership_divergence",
                    "Replica set %s has divergent member lists across rs.status views: %s."
                    % (replica_set_id, detail),
                    evidence_refs,
                    ["replica_set_config_divergence", "split_brain_enabling_condition"],
                    [],
                    "high",
                )
            )

        voting_counts = {_number(item.get("voting_members_count")) for item in records if item.get("voting_members_count") is not None}
        if len(voting_counts) > 1:
            detail = ", ".join(
                "%s voting_members_count=%s"
                % (_text(item.get("source_pod_ref")), _number(item.get("voting_members_count")))
                for item in records
            )
            findings.append(
                _finding(
                    "mongodb.replica_set.quorum_divergence",
                    "Replica set %s has divergent voting quorum views: %s."
                    % (replica_set_id, detail),
                    evidence_refs,
                    ["replica_set_config_divergence", "split_brain_enabling_condition"],
                    [],
                    "high",
                )
            )
    return findings


def network_counter_findings(structured_record: Dict[str, Any]) -> List[Dict[str, Any]]:
    details = (structured_record or {}).get("details") or {}
    network_overlay = details.get("network_overlay") or {}
    checks = [item for item in network_overlay.get("pod_connectivity_checks") or [] if isinstance(item, dict)]
    mongo_tcp_success = [
        item
        for item in checks
        if str(item.get("status") or "") == "success" and str(item.get("target_port") or "") == "27017"
    ]
    if not mongo_tcp_success:
        return []
    examples = ", ".join(
        "%s -> %s:%s"
        % (_text(item.get("source_pod_ref")), _text(item.get("target_ref") or item.get("target_ip")), _text(item.get("target_port")))
        for item in mongo_tcp_success[:4]
    )
    return [
        _finding(
            "mongodb.network.current_tcp_reachability",
            "Current MongoDB TCP probes succeeded for at least one member path: %s."
            % examples,
            ["structured_record.details.network_overlay.pod_connectivity_checks"],
            [],
            ["sustained_network_partition"],
            "medium",
        )
    ]


def history_log_findings(signal_bundle: Dict[str, Any]) -> List[Dict[str, Any]]:
    highlights = [item for item in (signal_bundle or {}).get("log_highlights") or [] if isinstance(item, dict)]
    matched = []
    for item in highlights:
        category = _text(item.get("category")).lower()
        message = _text(item.get("message") or item.get("detail"))
        lowered = message.lower()
        if category in {"election", "heartbeat", "reconfig", "stepdown"} or any(
            token in lowered
            for token in (
                "heartbeat",
                "hostunreachable",
                "election",
                "stepdown",
                "step down",
                "transition to primary",
                "setting node as primary",
                "reconfig",
                "rsconfig",
            )
        ):
            matched.append(item)
    if not matched:
        return []
    examples = "; ".join(
        "pod/%s %s: %s"
        % (
            _text(item.get("pod_ref") or item.get("object_ref")) or "unknown",
            _text(item.get("category")) or "log",
            _text(item.get("message") or item.get("detail"))[:220],
        )
        for item in matched[:3]
    )
    return [
        _finding(
            "mongodb.replica_set.history_election_heartbeat_logs",
            "MongoDB logs contain heartbeat/election/reconfig evidence around the split-brain path: %s."
            % examples,
            ["signal_bundle.log_highlights"],
            ["historical_network_or_heartbeat_partition", "mongodb_heartbeat_or_auth_layer_failure"],
            [],
            "high",
        )
    ]


def enabling_cause_candidate_findings(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    finding_ids = {str(item.get("finding_id") or "") for item in findings if isinstance(item, dict)}
    has_split_brain_invariant = bool(
        finding_ids
        & {
            "mongodb.replica_set.config_divergence",
            "mongodb.replica_set.membership_divergence",
            "mongodb.replica_set.quorum_divergence",
        }
    )
    if not has_split_brain_invariant:
        return []
    refutes_sustained_network_partition = "mongodb.network.current_tcp_reachability" in finding_ids
    statement = (
        "Replica set split-brain evidence should be deepened into enabling-cause candidates: "
        "historical network or heartbeat partition, replica set reconfig/member metadata drift, "
        "or MongoDB heartbeat/authentication/process-layer failure."
    )
    if refutes_sustained_network_partition:
        statement += " Current TCP/27017 reachability weakens an ongoing network partition, so history and MongoDB-level heartbeat evidence are required."
    return [
        _finding(
            "mongodb.replica_set.enabling_cause_candidates",
            statement,
            ["structured_record.details.replica_members"],
            [
                "historical_network_or_heartbeat_partition",
                "reconfig_or_member_config_drift",
                "mongodb_heartbeat_or_auth_layer_failure",
            ],
            ["sustained_network_partition"] if refutes_sustained_network_partition else [],
            "medium",
        )
    ]


def build_mongodb_deepening_findings(structured_record: Dict[str, Any], signal_bundle: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    details = (structured_record or {}).get("details") or {}
    member_records = [item for item in details.get("replica_members") or [] if isinstance(item, dict)]
    findings = []
    findings.extend(replica_set_invariant_findings(member_records))
    findings.extend(network_counter_findings(structured_record))
    findings.extend(history_log_findings(signal_bundle or {}))
    findings.extend(enabling_cause_candidate_findings(findings))
    return findings
