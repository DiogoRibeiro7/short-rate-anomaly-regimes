"""Environment manifest generation."""

from __future__ import annotations

import io
import json
import platform
import subprocess
import sys
from contextlib import redirect_stdout
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

import numpy as np

from short_rate_anomaly_regimes.provenance import sha256_file


def git_commit(cwd: Path = Path(".")) -> str:
    """Return the current Git commit, or ``unknown`` outside Git."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=cwd,
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip()


def git_dirty(cwd: Path = Path(".")) -> bool:
    """Return whether the Git working tree has uncommitted tracked changes."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=cwd,
        capture_output=True,
        check=False,
        text=True,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def package_versions() -> dict[str, str]:
    """Return installed Python package versions keyed by normalized package name."""
    versions: dict[str, str] = {}
    for distribution in metadata.distributions():
        name = distribution.metadata.get("Name")
        if name:
            versions[name.lower()] = distribution.version
    return dict(sorted(versions.items()))


def blas_information() -> dict[str, list[str]]:
    """Capture NumPy's BLAS/LAPACK configuration as text lines."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        np.show_config()
    return {"numpy_show_config": buffer.getvalue().splitlines()}


def build_environment_manifest(
    *,
    config_paths: tuple[Path, ...],
    cwd: Path = Path("."),
) -> dict[str, Any]:
    """Build a machine-readable manifest for the current execution environment."""
    return {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "python": {
            "version": platform.python_version(),
            "executable": sys.executable,
            "implementation": platform.python_implementation(),
        },
        "os": {
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
        },
        "packages": package_versions(),
        "blas": blas_information(),
        "git": {
            "commit": git_commit(cwd),
            "dirty": git_dirty(cwd),
        },
        "config_hashes": {str(path): sha256_file(path) for path in config_paths},
    }


def write_environment_manifest(
    *,
    output_path: Path,
    config_paths: tuple[Path, ...],
    cwd: Path = Path("."),
) -> None:
    """Write an environment manifest as stable JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_environment_manifest(config_paths=config_paths, cwd=cwd)
    output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
