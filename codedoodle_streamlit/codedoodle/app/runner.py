"""Runs generated code with hard limits.

IMPORTANT: this is a guard rail for demos on your own machine, not a security
boundary. Code runs as the same OS user as the server. For a public deployment
set ENABLE_RUN=0, or move execution to a separate, network-less runner service
(Piston, Judge0, a Firecracker/gVisor sandbox).

What it does:
  * temp working directory, deleted afterwards
  * stripped environment (your API key is NOT passed to the program)
  * CPU time, memory, file-size and process-count limits (via a launcher)
  * wall-clock timeout that kills the whole process group
  * output captured through size-capped files, then truncated
  * no network, when the host allows `unshare -rn`
"""

import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from functools import lru_cache
from pathlib import Path

SUPPORTED = ("python", "cpp")
RUN_TIMEOUT = 5          # seconds of wall-clock time for the program
COMPILE_TIMEOUT = 20     # seconds for g++
MAX_OUTPUT = 20_000      # characters returned per stream
MEM_LIMIT = 512 * 1024 * 1024
FILE_LIMIT = 5_000_000   # bytes any single file (including captured output) may reach

# Sets resource limits, then replaces itself with the real program.
_LAUNCHER = """
import os, resource, sys
cpu, mem = int(sys.argv[1]), int(sys.argv[2])
resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
resource.setrlimit(resource.RLIMIT_FSIZE, (%d, %d))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
cmd = sys.argv[3:]
os.execv(cmd[0], cmd)
""" % (FILE_LIMIT, FILE_LIMIT)


def run_enabled() -> bool:
    return os.getenv("ENABLE_RUN", "1") != "0"


@lru_cache(maxsize=1)
def network_isolated() -> bool:
    """True if we can start programs in an empty network namespace."""
    if not shutil.which("unshare"):
        return False
    try:
        return subprocess.run(["unshare", "-rn", "true"], capture_output=True, timeout=5).returncode == 0
    except Exception:
        return False


def _clean_env(workdir: str) -> dict:
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": workdir,
        "TMPDIR": workdir,
        "LANG": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def _read_capped(path: Path) -> str:
    data = path.read_bytes()[: MAX_OUTPUT + 1]
    text = data.decode("utf-8", errors="replace")
    if len(text) > MAX_OUTPUT:
        text = text[:MAX_OUTPUT] + "\n[output truncated]"
    return text


def _signal_note(returncode: int) -> str:
    if returncode >= 0:
        return ""
    try:
        name = signal.Signals(-returncode).name
    except ValueError:
        name = str(-returncode)
    hints = {
        "SIGXCPU": "CPU time limit reached",
        "SIGXFSZ": "output size limit reached",
        "SIGKILL": "killed (time or memory limit)",
        "SIGSEGV": "segmentation fault",
    }
    return f"\n[process ended: {hints.get(name, name)}]"


def _execute(program: list, stdin_text: str, workdir: Path, timeout: float) -> dict:
    """Run `program` (absolute paths) under the launcher with limits."""
    stdin_path, out_path, err_path = workdir / "stdin.txt", workdir / "stdout.txt", workdir / "stderr.txt"
    stdin_path.write_text(stdin_text, encoding="utf-8")

    cmd = [sys.executable, "-I", "-c", _LAUNCHER, str(int(timeout) + 1), str(MEM_LIMIT), *program]
    if network_isolated():
        cmd = ["unshare", "-rn", *cmd]

    started = time.monotonic()
    timed_out = False
    with open(stdin_path, "rb") as fin, open(out_path, "wb") as fout, open(err_path, "wb") as ferr:
        proc = subprocess.Popen(
            cmd, stdin=fin, stdout=fout, stderr=ferr, cwd=workdir,
            env=_clean_env(str(workdir)), start_new_session=True,
        )
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()

    stderr = _read_capped(err_path)
    if timed_out:
        stderr += f"\n[stopped: still running after {timeout:g} seconds]"
    else:
        stderr += _signal_note(proc.returncode)
    return {
        "stdout": _read_capped(out_path),
        "stderr": stderr.strip("\n"),
        "exit_code": None if timed_out else proc.returncode,
        "timed_out": timed_out,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "phase": "run",
    }


def run_code(language: str, code: str, stdin_text: str = "", timeout: float = RUN_TIMEOUT) -> dict:
    if language not in SUPPORTED:
        raise ValueError(f"Unsupported language: {language}")

    workdir = Path(tempfile.mkdtemp(prefix="codedoodle_"))
    try:
        if language == "python":
            src = workdir / "main.py"
            src.write_text(code, encoding="utf-8")
            return _execute([sys.executable, "-I", str(src)], stdin_text, workdir, timeout)

        # C++: compile first, then run the binary.
        src, binary = workdir / "main.cpp", workdir / "prog"
        src.write_text(code, encoding="utf-8")
        gpp = shutil.which("g++")
        if not gpp:
            return {"stdout": "", "stderr": "g++ is not installed on this server, so C++ cannot be run.",
                    "exit_code": 1, "timed_out": False, "duration_ms": 0, "phase": "compile"}
        started = time.monotonic()
        try:
            build = subprocess.run(
                [gpp, "-std=c++17", "-O1", "-o", str(binary), str(src)],
                cwd=workdir, env=_clean_env(str(workdir)), capture_output=True, timeout=COMPILE_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": f"[compile stopped after {COMPILE_TIMEOUT} seconds]",
                    "exit_code": None, "timed_out": True, "duration_ms": COMPILE_TIMEOUT * 1000, "phase": "compile"}
        if build.returncode != 0:
            text = build.stderr.decode("utf-8", errors="replace")[:MAX_OUTPUT]
            return {"stdout": "", "stderr": text.replace(str(workdir) + "/", ""),
                    "exit_code": build.returncode, "timed_out": False,
                    "duration_ms": int((time.monotonic() - started) * 1000), "phase": "compile"}
        return _execute([str(binary)], stdin_text, workdir, timeout)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
