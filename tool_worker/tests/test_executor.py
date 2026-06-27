"""Sandbox executor tests — proves real code runs with real output, and that the
network is blocked, timeouts are enforced, and output is capped.
"""

from __future__ import annotations

from executor import run_code


def test_runs_and_captures_real_stdout():
    res = run_code("print('hello from sandbox')")
    assert res.status == "ok"
    assert res.return_code == 0
    assert "hello from sandbox" in res.stdout


def test_compute_works():
    res = run_code("print(sum(range(10)))")
    assert res.status == "ok"
    assert res.stdout.strip() == "45"


def test_network_is_blocked():
    code = (
        "import socket\n"
        "try:\n"
        "    socket.create_connection(('1.1.1.1', 80), timeout=1)\n"
        "    print('CONNECTED')\n"
        "except Exception as e:\n"
        "    print('BLOCKED', type(e).__name__)\n"
    )
    res = run_code(code)
    assert "CONNECTED" not in res.stdout
    assert "BLOCKED" in res.stdout


def test_socket_constructor_blocked():
    res = run_code("import socket; socket.socket()")
    assert res.status == "error"
    assert "network access is disabled" in res.stderr


def test_timeout_enforced():
    res = run_code("import time; time.sleep(10)", timeout_seconds=1)
    assert res.status == "timeout"
    assert res.timed_out is True


def test_output_is_capped():
    res = run_code("print('x' * 100000)", max_output_bytes=1000)
    assert "truncated" in res.stdout
    assert len(res.stdout.encode("utf-8")) <= 1000 + 64  # cap + marker slack


def test_nonzero_exit_is_error():
    res = run_code("raise ValueError('boom')")
    assert res.status == "error"
    assert "ValueError" in res.stderr
