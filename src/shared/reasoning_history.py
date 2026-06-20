"""Append-only reasoning history helpers for incident analysis."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .analysis_common import as_list
from .workspace import load_yaml, now_iso, write_yaml


REASONING_DIRNAME = "reasoning"
REASONING_MANIFEST_FILENAME = "reasoning-manifest.yaml"
REASONING_HISTORY_SCHEMA_VERSION = "reasoning-history.v1"
REASONING_SEGMENT_SCHEMA_VERSION = "reasoning-segment.v1"


DEFAULT_SHARED_EVIDENCE_REFS = (
    "input.yaml",
    "structured_record.yaml",
    "signal_bundle.yaml",
    "collection_report.yaml",
)
OPTIONAL_SHARED_EVIDENCE_REFS = (
    "analysis.rules-fallback.yaml",
    "analysis.multitrack.yaml",
    "deep-analysis.yaml",
    "agent-reasoning-task.md",
    "reasoning-board.yaml",
)


def reasoning_manifest_file(incident_dir: Path) -> Path:
    return incident_dir / REASONING_MANIFEST_FILENAME


def reasoning_dir(incident_dir: Path) -> Path:
    return incident_dir / REASONING_DIRNAME


def current_head_segment_id(incident_dir: Path) -> Optional[str]:
    latest = _current_head_segment_record(incident_dir)
    if latest is None:
        return None
    segment_id = str(latest.get("segment_id") or "").strip()
    return segment_id or None


def current_head_analysis_hash(incident_dir: Path) -> Optional[str]:
    latest = _current_head_segment_record(incident_dir)
    if latest is None:
        return None
    analysis_hash = str(latest.get("analysis_sha256") or "").strip()
    return analysis_hash or None


def current_head_segment_path(incident_dir: Path) -> Optional[Path]:
    manifest_file = reasoning_manifest_file(incident_dir)
    if not manifest_file.exists():
        return None
    manifest = load_yaml(manifest_file)
    current_head = str(manifest.get("current_head") or "").strip()
    if current_head:
        path = incident_dir / current_head
        return path if path.exists() else None
    latest = _current_head_segment_record(incident_dir)
    if latest is None:
        return None
    path = incident_dir / str(latest.get("path") or "")
    return path if path.exists() else None


def _current_head_segment_record(incident_dir: Path) -> Optional[Dict[str, Any]]:
    manifest_file = reasoning_manifest_file(incident_dir)
    if not manifest_file.exists():
        return None
    manifest = load_yaml(manifest_file)
    segments = as_list(manifest.get("segments"))
    if not segments:
        return None
    current_head = str(manifest.get("current_head") or "").strip()
    if current_head:
        for item in segments:
            if isinstance(item, dict) and str(item.get("path") or "").strip() == current_head:
                return item
    latest = segments[-1]
    if not isinstance(latest, dict):
        return None
    return latest


def analysis_content_hash(analysis: Dict[str, Any]) -> str:
    encoded = json.dumps(analysis, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def write_reasoning_segment(
    incident_dir: Path,
    source: str,
    analysis: Dict[str, Any],
    *,
    summary: str,
    depends_on: Optional[List[str]] = None,
    supersedes: Optional[List[str]] = None,
    input_refs: Optional[List[str]] = None,
    output_refs: Optional[Dict[str, str]] = None,
    executed_validations: Optional[List[Dict[str, Any]]] = None,
) -> Path:
    """Write an immutable reasoning segment and update the mutable manifest."""

    clean_source = _slug(source)
    segment_number = _next_segment_number(incident_dir)
    segment_id = "%04d-%s" % (segment_number, clean_source)
    segment_relpath = "%s/%s.yaml" % (REASONING_DIRNAME, segment_id)
    segment_path = incident_dir / segment_relpath
    if segment_path.exists():
        raise FileExistsError("reasoning segment already exists: %s" % segment_path)

    created_at = now_iso()
    shared_refs = _shared_evidence_refs(incident_dir, input_refs)
    output_refs = output_refs or {"analysis": "analysis.yaml", "report": "report.md"}
    segment = {
        "schema_version": REASONING_SEGMENT_SCHEMA_VERSION,
        "segment_id": segment_id,
        "source": source,
        "created_at": created_at,
        "incident_id": incident_dir.name,
        "summary": summary,
        "depends_on": depends_on or [],
        "supersedes": supersedes or [],
        "analysis_sha256": analysis_content_hash(analysis),
        "shared_evidence_pool": _shared_evidence_pool(shared_refs),
        "materialized_outputs": _copy_yaml_value(output_refs),
        "executed_validations": _copy_yaml_value(executed_validations or []),
        "hypothesis_validations": analysis_to_hypothesis_validations(analysis, segment_relpath, shared_refs),
        "agent_conclusion_gate": _copy_yaml_value(_agent_conclusion_gate(analysis)),
        "conclusion_delta": _conclusion_delta(analysis),
        "analysis_snapshot": _copy_yaml_value(analysis),
    }

    write_yaml(segment_path, segment)
    _update_manifest(
        incident_dir,
        segment_id=segment_id,
        segment_relpath=segment_relpath,
        source=source,
        created_at=created_at,
        summary=summary,
        analysis_hash=segment["analysis_sha256"],
        depends_on=depends_on or [],
        supersedes=supersedes or [],
        shared_refs=shared_refs,
        output_refs=output_refs,
        agent_conclusion_gate=segment["agent_conclusion_gate"],
    )
    return segment_path


def analysis_to_hypothesis_validations(
    analysis: Dict[str, Any],
    segment_relpath: str,
    shared_refs: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    validations: List[Dict[str, Any]] = []
    verification_requests = _verification_requests_by_hypothesis(analysis)
    for index, hypothesis in enumerate(as_list(analysis.get("hypotheses")), start=1):
        if not isinstance(hypothesis, dict):
            continue
        hypothesis_id = str(hypothesis.get("hypothesis_id") or "H%s" % index).strip()
        private_ref = "%s#hypothesis_validations[%s]" % (segment_relpath, hypothesis_id)
        validations.append(
            {
                "hypothesis_id": hypothesis_id,
                "statement": str(hypothesis.get("statement") or "").strip(),
                "isolation": {
                    "scope": "hypothesis_validation",
                    "shared_read_refs": [item["path"] for item in shared_refs],
                    "private_write_ref": private_ref,
                    "rule": "read shared evidence; publish only this hypothesis validation record",
                },
                "isolated_inputs": {
                    "supporting_evidence": _copy_yaml_value(as_list(hypothesis.get("supporting_evidence"))),
                    "counter_evidence": _copy_yaml_value(as_list(hypothesis.get("counter_evidence"))),
                    "evidence_gaps": _copy_yaml_value(as_list(hypothesis.get("evidence_gaps"))),
                    "validation_actions": _copy_yaml_value(as_list(hypothesis.get("validation_actions"))),
                },
                "verification_requests": _copy_yaml_value(verification_requests.get(hypothesis_id, [])),
                "result": {
                    "status": str(hypothesis.get("status") or "").strip(),
                    "validation_result": str(hypothesis.get("validation_result") or hypothesis.get("status") or "").strip(),
                },
                "publishes": {
                    "supporting_evidence": _copy_yaml_value(as_list(hypothesis.get("supporting_evidence"))),
                    "counter_evidence": _copy_yaml_value(as_list(hypothesis.get("counter_evidence"))),
                    "evidence_gaps": _copy_yaml_value(as_list(hypothesis.get("evidence_gaps"))),
                },
            }
        )
    return validations


def _update_manifest(
    incident_dir: Path,
    *,
    segment_id: str,
    segment_relpath: str,
    source: str,
    created_at: str,
    summary: str,
    analysis_hash: str,
    depends_on: List[str],
    supersedes: List[str],
    shared_refs: List[Dict[str, str]],
    output_refs: Dict[str, str],
    agent_conclusion_gate: Dict[str, Any],
) -> None:
    manifest_file = reasoning_manifest_file(incident_dir)
    if manifest_file.exists():
        manifest = load_yaml(manifest_file)
    else:
        manifest = {
            "schema_version": REASONING_HISTORY_SCHEMA_VERSION,
            "incident_id": incident_dir.name,
            "segments": [],
        }
    manifest["schema_version"] = REASONING_HISTORY_SCHEMA_VERSION
    manifest["incident_id"] = str(manifest.get("incident_id") or incident_dir.name)
    manifest["current_head"] = segment_relpath
    manifest["updated_at"] = created_at
    manifest["materialized_outputs"] = output_refs
    manifest["shared_evidence_pool"] = _shared_evidence_pool(shared_refs)
    manifest["isolation_model"] = {
        "shared_readonly_refs": [item["path"] for item in shared_refs],
        "isolated_validation_prefix": "reasoning/*.yaml#hypothesis_validations",
        "rule": "hypothesis validations may read shared evidence but must not mutate another hypothesis validation record",
    }
    segments = as_list(manifest.get("segments"))
    segments.append(
        {
            "segment_id": segment_id,
            "path": segment_relpath,
            "source": source,
            "created_at": created_at,
            "summary": summary,
            "analysis_sha256": analysis_hash,
            "depends_on": depends_on,
            "supersedes": supersedes,
            "output_refs": output_refs,
            "agent_conclusion_gate": _agent_conclusion_gate_summary(agent_conclusion_gate),
        }
    )
    manifest["segments"] = segments
    write_yaml(manifest_file, manifest)


def _shared_evidence_refs(incident_dir: Path, input_refs: Optional[List[str]]) -> List[Dict[str, str]]:
    refs = input_refs or _default_shared_evidence_refs(incident_dir)
    result: List[Dict[str, str]] = []
    for ref in refs:
        ref_text = str(ref).strip()
        if not ref_text:
            continue
        item = {"path": ref_text, "access": "read_only"}
        if (incident_dir / ref_text).exists():
            item["status"] = "present"
        else:
            item["status"] = "missing"
        result.append(item)
    return result


def _default_shared_evidence_refs(incident_dir: Path) -> List[str]:
    refs = list(DEFAULT_SHARED_EVIDENCE_REFS)
    refs.extend(ref for ref in OPTIONAL_SHARED_EVIDENCE_REFS if (incident_dir / ref).exists())
    return refs


def _shared_evidence_pool(shared_refs: List[Dict[str, str]]) -> Dict[str, Any]:
    return {
        "access": "read_only",
        "refs": shared_refs,
    }


def _next_segment_number(incident_dir: Path) -> int:
    max_number = 0
    pattern = re.compile(r"^(\d{4})-.+\.ya?ml$")
    for path in reasoning_dir(incident_dir).glob("*.y*ml"):
        match = pattern.match(path.name)
        if match:
            max_number = max(max_number, int(match.group(1)))
    return max_number + 1


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "reasoning"


def _verification_requests_by_hypothesis(analysis: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    result: Dict[str, List[Dict[str, Any]]] = {}
    for item in as_list(analysis.get("verification_requests")):
        if not isinstance(item, dict):
            continue
        hypothesis_id = str(item.get("hypothesis_id") or "").strip()
        if not hypothesis_id:
            continue
        result.setdefault(hypothesis_id, []).append(item)
    return result


def _conclusion_delta(analysis: Dict[str, Any]) -> Dict[str, Any]:
    conclusion = analysis.get("conclusion_summary")
    if not isinstance(conclusion, dict):
        return {}
    keys = ("statement", "confidence", "deepest_supported_level", "primary_cause_category", "impact_scope")
    return {key: conclusion.get(key) for key in keys if key in conclusion}


def _agent_conclusion_gate(analysis: Dict[str, Any]) -> Dict[str, Any]:
    gate = analysis.get("agent_conclusion_gate")
    return gate if isinstance(gate, dict) else {}


def _agent_conclusion_gate_summary(gate: Dict[str, Any]) -> Dict[str, Any]:
    if not gate:
        return {}
    blockers = as_list(gate.get("blockers"))
    return {
        "decision": str(gate.get("decision") or "").strip(),
        "override_applied": bool(gate.get("override_applied", False)),
        "blocker_count": len([item for item in blockers if isinstance(item, dict)]),
    }


def _copy_yaml_value(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))
