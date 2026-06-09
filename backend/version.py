"""
Single source of truth for the application version.

APP_VERSION is read from pyproject.toml at import time using the stdlib
tomllib module (Python 3.11+).  Bump the version in pyproject.toml only
— this file never needs touching.

GIT_HASH and BUILD_TIME are injected at image build time by the Dockerfile
via a generated _version_meta.py module.  When running outside Docker (e.g.
local development) sensible fallback values are used.
"""

import tomllib
from datetime import UTC
from pathlib import Path

try:
    with open(Path(__file__).parent / "pyproject.toml", "rb") as _f:
        APP_VERSION: str = tomllib.load(_f)["project"]["version"]
except (FileNotFoundError, KeyError):
    APP_VERSION = "0.0.0"

# The current API version prefix. Increment this (v2, v3…) when making
# breaking changes to the REST API. Non-breaking additions stay on v1.
API_VERSION = "v1"

try:
    from _version_meta import BUILD_GIT_HASH, BUILD_TIME  # type: ignore[import]
except ImportError:
    # Not running inside a Docker image — try to read the values live from git.
    import subprocess
    from datetime import datetime
    from pathlib import Path

    def _find_git_root() -> Path | None:
        """Walk up from this file's location to find the .git directory."""
        current = Path(__file__).resolve().parent
        for candidate in [current, *current.parents]:
            if (candidate / ".git").exists():
                return candidate
        return None

    def _git(cmd: list[str], cwd: Path | None) -> str:
        try:
            return subprocess.check_output(  # noqa: S603
                ["git", *cmd],
                cwd=cwd,
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
        except Exception:
            return ""

    _git_root = _find_git_root()
    BUILD_GIT_HASH = _git(["rev-parse", "--short", "HEAD"], _git_root) or "dev"
    BUILD_TIME = (
        datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if BUILD_GIT_HASH != "dev" else "unknown"
    )

__all__ = ["API_VERSION", "APP_VERSION", "BUILD_GIT_HASH", "BUILD_TIME"]
