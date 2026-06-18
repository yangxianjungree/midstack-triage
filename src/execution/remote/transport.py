"""Remote transport interface for execution-plane commands and file copy."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess
import shutil
import subprocess
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


@dataclass(frozen=True)
class LocalTransport:
    """RemoteTransport implementation that runs commands on the local machine."""

    def run(self, access: Dict[str, Any], remote_script: str, timeout: int = 60) -> CompletedProcess:
        del access
        return subprocess.run(
            ["bash", "-lc", remote_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=timeout,
        )

    def copy_to(self, access: Dict[str, Any], local_path: Path, remote_path: str) -> None:
        del access
        destination = Path(remote_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(local_path, destination)
        except OSError as exc:
            raise RuntimeError("local copy_to failed for %s: %s" % (local_path, exc)) from exc

    def copy_from(self, access: Dict[str, Any], remote_path: str, local_path: Path, recursive: bool = False) -> None:
        del access
        source = Path(remote_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if recursive:
                if local_path.exists():
                    shutil.rmtree(local_path)
                shutil.copytree(source, local_path)
                return
            shutil.copy2(source, local_path)
        except OSError as exc:
            raise RuntimeError("local copy_from failed for %s: %s" % (remote_path, exc)) from exc
