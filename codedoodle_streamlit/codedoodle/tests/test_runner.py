import os
import shutil

import pytest

from app import runner

needs_gpp = pytest.mark.skipif(shutil.which("g++") is None, reason="g++ not installed")


def test_python_hello():
    r = runner.run_code("python", 'print("hi")')
    assert r["stdout"].strip() == "hi"
    assert r["exit_code"] == 0 and not r["timed_out"]


def test_python_reads_stdin():
    r = runner.run_code("python", "print(int(input()) * 2)", stdin_text="21\n")
    assert r["stdout"].strip() == "42"


def test_python_runtime_error_reports_traceback():
    r = runner.run_code("python", "print(1/0)")
    assert r["exit_code"] == 1
    assert "ZeroDivisionError" in r["stderr"]


def test_python_infinite_loop_is_stopped():
    r = runner.run_code("python", "while True: pass", timeout=1)
    assert r["timed_out"] is True
    assert r["duration_ms"] < 4000


def test_api_key_is_not_visible_to_generated_code(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret")
    r = runner.run_code("python", "import os; print(os.environ.get('GEMINI_API_KEY'))")
    assert r["stdout"].strip() == "None"


def test_huge_output_is_truncated():
    r = runner.run_code("python", "print('x' * 200000)")
    assert len(r["stdout"]) <= runner.MAX_OUTPUT + 50
    assert "truncated" in r["stdout"]


@needs_gpp
def test_cpp_hello_with_stdin():
    code = '#include <iostream>\nint main(){int n; std::cin>>n; std::cout<<n+1<<std::endl;}'
    r = runner.run_code("cpp", code, stdin_text="41")
    assert r["stdout"].strip() == "42"
    assert r["phase"] == "run"


@needs_gpp
def test_cpp_compile_error_is_reported():
    r = runner.run_code("cpp", "int main(){ return x; }")
    assert r["phase"] == "compile"
    assert r["exit_code"] != 0
    assert "error" in r["stderr"]


def test_unsupported_language():
    with pytest.raises(ValueError):
        runner.run_code("ruby", "puts 1")
