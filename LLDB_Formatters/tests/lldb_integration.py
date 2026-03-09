import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPO_ROOT / "LLDB_Formatters"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
RUNTIME_ROOT = REPO_ROOT / ".tmp" / "lldb_integration"


def _tool_path(candidates):
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def find_compiler():
    return _tool_path(["clang++", "c++"])


def find_lldb():
    return _tool_path(["lldb"])


def integration_environment():
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    tmpdir = RUNTIME_ROOT / "tmp"
    home = RUNTIME_ROOT / "home"
    cache = RUNTIME_ROOT / "cache"
    tmpdir.mkdir(parents=True, exist_ok=True)
    home.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["TMPDIR"] = str(tmpdir)
    env["HOME"] = str(home)
    env["XDG_CACHE_HOME"] = str(cache)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def build_fixture(fixture_name):
    compiler = find_compiler()
    if not compiler:
        raise unittest.SkipTest("C++ compiler not available for LLDB integration tests.")

    source_path = FIXTURES_DIR / fixture_name
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    build_dir = Path(tempfile.mkdtemp(prefix="fixture-", dir=RUNTIME_ROOT))
    binary_path = build_dir / source_path.stem

    compile_cmd = [
        compiler,
        "-std=c++17",
        "-g",
        "-O0",
        str(source_path),
        "-o",
        str(binary_path),
    ]
    result = subprocess.run(
        compile_cmd,
        cwd=REPO_ROOT,
        env=integration_environment(),
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to compile fixture '{fixture_name}'.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )

    return binary_path


def run_lldb_batch(binary_path, commands):
    lldb_path = find_lldb()
    if not lldb_path:
        raise unittest.SkipTest("LLDB not available for integration tests.")

    lldb_cmd = [
        lldb_path,
        "-b",
        "-Q",
        str(binary_path),
        "-o",
        f"command script import {PACKAGE_ROOT}",
        "-o",
        "breakpoint set --name break_here",
        "-o",
        "run",
        "-o",
        "up",
    ]
    for command in commands:
        lldb_cmd.extend(["-o", command])
    lldb_cmd.extend(["-o", "quit"])

    result = subprocess.run(
        lldb_cmd,
        cwd=REPO_ROOT,
        env=integration_environment(),
        text=True,
        capture_output=True,
    )
    return result


def strip_ansi(text):
    result = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\x1b":
            end = index + 1
            while end < len(text) and text[end] != "m":
                end += 1
            index = min(end + 1, len(text))
            continue
        result.append(char)
        index += 1
    return "".join(result)
