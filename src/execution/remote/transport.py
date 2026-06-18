"""Remote transport interface for execution-plane commands and file copy."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any, Callable, Dict, Protocol


RunSshFn = Callable[[Dict[str, Any], str, int], CompletedProcess]
ScpToFn = Callable[[Dict[str, Any], Path, str], None]
ScpFromFn = Callable[[Dict[str, Any], str, Path, bool], None]


class RemoteTransport(Protocol):
    def run(self, access: Dict[str, Any], remote_script: str, timeout: int = 60) -> CompletedProcess:
        ...

    def copy_to(self, access: Dict[str, Any], local_path: Path, remote_path: str) -> None:
        ...

    def copy_from(self, access: Dict[str, Any], remote_path: str, local_path: Path, recursive: bool = False) -> None:
        ...


@dataclass(frozen=True)
class FunctionRemoteTransport:
    """RemoteTransport backed by the current ssh/scp function implementations."""

    run_ssh_fn: RunSshFn
    scp_to_fn: ScpToFn
    scp_from_fn: ScpFromFn

    def run(self, access: Dict[str, Any], remote_script: str, timeout: int = 60) -> CompletedProcess:
        return self.run_ssh_fn(access, remote_script, timeout)

    def copy_to(self, access: Dict[str, Any], local_path: Path, remote_path: str) -> None:
        self.scp_to_fn(access, local_path, remote_path)

    def copy_from(self, access: Dict[str, Any], remote_path: str, local_path: Path, recursive: bool = False) -> None:
        self.scp_from_fn(access, remote_path, local_path, recursive)
