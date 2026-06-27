"""Network-less, resource-limited Python code executor.

This is the ONLY place untrusted code runs. Defense in depth:

  * Process isolation: code runs in a fresh subprocess, not the worker process.
  * No network: a preamble disables the `socket` module before user code runs, and
    the worker container itself has no external route (compose `internal` network +
    cap_drop). The preamble blocks the common path; the container is the hard wall.
  * Resource limits: RLIMIT_CPU (seconds), RLIMIT_AS (address space / memory),
    RLIMIT_FSIZE (file writes), and a wall-clock timeout that kills the process.
  * Clean environment: the child gets a minimal env, so no host secrets (API keys)
    leak into untrusted code.
  * Output cap: stdout/stderr are truncated to a maximum byte budget.

`run_code` is a plain function so it can be unit-tested directly, and is also what
worker.py calls for each queued job.
"""

from __future__ import annotations

import os
import resource
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass

# Prepended to every submission. Disables sockets and a few obvious escapes.
_PREAMBLE = (
    "import socket as _s\n"
    "def _blocked(*a, **k):\n"
    "    raise OSError('network access is disabled in the ApexMind sandbox')\n"
    "_s.socket = _blocked\n"
    "_s.create_connection = _blocked\n"
    "_s.socketpair = _blocked\n"
    "del _s\n"
    "# --- user code below ---\n"
)


@dataclass
class ExecResult:
    status: str  # ok | error | timeout
    stdout: str
    stderr: str
    return_code: int | None
    duration_ms: int
    timed_out: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _limits(cpu_seconds: int, mem_bytes: int, fsize_bytes: int):
    def _set() -> None:
        # CPU time (SIGXCPU then SIGKILL on hard limit)
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
        # Address space (virtual memory)
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        # Max bytes the process may write to files
        resource.setrlimit(resource.RLIMIT_FSIZE, (fsize_bytes, fsize_bytes))
        # No core dumps
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        # New session so we can kill the whole group on timeout
        os.setsid()

    return _set


def run_code(
    code: str,
    *,
    timeout_seconds: int = 10,
    mem_mb: int = 256,
    max_output_bytes: int = 65536,
    fsize_mb: int = 8,
) -> ExecResult:
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="apex_sbx_") as tmp:
        script = os.path.join(tmp, "submission.py")
        with open(script, "w") as f:
            f.write(_PREAMBLE + code)

        # Minimal env: no inherited secrets, restricted PATH, cwd in the tmp dir.
        env = {
            "PATH": "/usr/bin:/bin",
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "HOME": tmp,
            "TMPDIR": tmp,
        }
        proc = subprocess.Popen(
            # -I: isolated mode (ignore env/user site); -S: no site
            [sys.executable, "-I", "-S", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=tmp,
            env=env,
            text=True,
            preexec_fn=_limits(
                cpu_seconds=timeout_seconds,
                mem_bytes=mem_mb * 1024 * 1024,
                fsize_bytes=fsize_mb * 1024 * 1024,
            ),
        )
        timed_out = False
        try:
            stdout, stderr = proc.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_group(proc)
            stdout, stderr = proc.communicate()

    duration_ms = int((time.monotonic() - started) * 1000)
    stdout = _truncate(stdout, max_output_bytes)
    stderr = _truncate(stderr, max_output_bytes)
    if timed_out:
        status = "timeout"
    elif proc.returncode == 0:
        status = "ok"
    else:
        status = "error"
    return ExecResult(
        status=status,
        stdout=stdout,
        stderr=stderr,
        return_code=proc.returncode,
        duration_ms=duration_ms,
        timed_out=timed_out,
    )


def _kill_group(proc: subprocess.Popen) -> None:
    import signal

    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):  # pragma: no cover
        proc.kill()


def _truncate(text: str, max_bytes: int) -> str:
    encoded = text.encode("utf-8", "replace")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", "ignore") + "\n…[output truncated]"
