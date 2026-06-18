"""Phase 2 inventory package."""

from .auth import (
    append_auth_secret_ref_candidate,
    auth_secret_ref_score,
    build_auth_hints,
    container_specs_for_auth,
    mongodb_auth_secret_refs,
)
from .events import related_event
from .targets import (
    append_unique,
    build_mongodb_targets,
    inventory_scope_objects,
)
from .topology import build_topology_hints, deployment_architecture_candidates
from .inventory import discover_mongodb_inventory
from .kubectl import run_remote_kubectl_json
from .objects import (
    MONGODB_DISCOVERY_HINTS,
    compact_k8s_object,
    condition_summary,
    deployment_architecture_hints,
    mongodb_role_hints,
    object_matches_mongodb,
    object_name,
    object_namespace,
)

__all__ = [
    "MONGODB_DISCOVERY_HINTS",
    "append_auth_secret_ref_candidate",
    "append_unique",
    "auth_secret_ref_score",
    "build_auth_hints",
    "build_mongodb_targets",
    "build_topology_hints",
    "compact_k8s_object",
    "condition_summary",
    "container_specs_for_auth",
    "deployment_architecture_candidates",
    "deployment_architecture_hints",
    "discover_mongodb_inventory",
    "inventory_scope_objects",
    "mongodb_auth_secret_refs",
    "mongodb_role_hints",
    "object_matches_mongodb",
    "object_name",
    "object_namespace",
    "related_event",
    "run_remote_kubectl_json",
]
