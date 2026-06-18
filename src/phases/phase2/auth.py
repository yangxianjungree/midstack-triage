"""Authentication hint helpers for Phase 2 inventory."""

from __future__ import annotations

from typing import Any, Dict, List

from .objects import object_name, object_namespace


def container_specs_for_auth(kind: str, obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    if kind == "Pod":
        spec = obj.get("spec") or {}
        return [item for item in (spec.get("containers") or []) if isinstance(item, dict)]
    if kind == "StatefulSet":
        spec = ((obj.get("spec") or {}).get("template") or {}).get("spec") or {}
        return [item for item in (spec.get("containers") or []) if isinstance(item, dict)]
    return []


def auth_secret_ref_score(env_name: str, key: str, roles: List[str], kind: str) -> int:
    score = 0
    text = ("%s %s" % (env_name, key)).lower()
    if "root" in text:
        score += 30
    if "password" in text:
        score += 20
    if "mongos" in roles or "configsvr" in roles or "shard" in roles or "replicaset" in roles:
        score += 10
    if kind == "StatefulSet":
        score += 5
    return score


def mongodb_auth_secret_refs(kind: str, obj: Dict[str, Any], roles: List[str]) -> List[Dict[str, Any]]:
    namespace = object_namespace(obj)
    source_name = object_name(obj)
    candidates = []
    for container in container_specs_for_auth(kind, obj):
        container_name = str(container.get("name") or "")
        for env in container.get("env") or []:
            if not isinstance(env, dict):
                continue
            secret_key_ref = (((env.get("valueFrom") or {}).get("secretKeyRef")) or {})
            secret_name = str(secret_key_ref.get("name") or "")
            secret_key = str(secret_key_ref.get("key") or "")
            if not secret_name or not secret_key:
                continue
            env_name = str(env.get("name") or "")
            candidates.append(
                {
                    "namespace": namespace,
                    "name": secret_name,
                    "key": secret_key,
                    "env_name": env_name,
                    "source_kind": kind,
                    "source_name": source_name,
                    "source_container": container_name,
                    "score": auth_secret_ref_score(env_name, secret_key, roles, kind),
                }
            )
    return candidates


def append_auth_secret_ref_candidate(target: List[Dict[str, Any]], candidate: Dict[str, Any]) -> None:
    key = (str(candidate.get("namespace") or ""), str(candidate.get("name") or ""), str(candidate.get("key") or ""))
    for index, existing in enumerate(target):
        existing_key = (str(existing.get("namespace") or ""), str(existing.get("name") or ""), str(existing.get("key") or ""))
        if existing_key == key:
            if int(candidate.get("score") or 0) > int(existing.get("score") or 0):
                target[index] = candidate
            return
    target.append(candidate)


def build_auth_hints(selected_namespace: str, auth_candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    scoped = [item for item in auth_candidates if str(item.get("namespace") or "") == selected_namespace]
    scoped.sort(key=lambda item: (-int(item.get("score") or 0), str(item.get("name") or ""), str(item.get("key") or "")))
    selected_secret_ref = {}
    if scoped:
        selected_secret_ref = {"namespace": str(scoped[0].get("namespace") or ""), "name": str(scoped[0].get("name") or ""), "key": str(scoped[0].get("key") or "")}
    return {"secret_ref_candidates": scoped, "selected_secret_ref": selected_secret_ref}
