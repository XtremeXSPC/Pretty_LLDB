import os
import shutil
import subprocess
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPO_ROOT / "LLDB_Formatters"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
RUNTIME_ROOT = REPO_ROOT / ".tmp" / "lldb_integration"


@dataclass(frozen=True)
class CompilerVariant:
    name: str
    compiler: str
    extra_flags: tuple[str, ...] = ()
    expected_abi: str | None = None


def _tool_path(candidates):
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def find_compiler():
    return _tool_path(["clang++", "c++"])


def find_compilers():
    resolved = []
    seen = set()
    for candidate in ["clang++", "g++", "c++"]:
        compiler = _tool_path([candidate])
        compiler_key = _compiler_version_text(compiler) if compiler else None
        if compiler and compiler_key not in seen:
            seen.add(compiler_key)
            resolved.append(compiler)
    return resolved


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


def _compiler_version_text(compiler):
    result = subprocess.run(
        [compiler, "--version"],
        env=integration_environment(),
        text=True,
        capture_output=True,
    )
    return f"{result.stdout}\n{result.stderr}".strip()


def _compiler_kind(compiler):
    version_text = _compiler_version_text(compiler).lower()
    if "clang" in version_text:
        return "clang"
    if "gcc" in version_text or "g++" in version_text:
        return "gcc"
    return "unknown"


def _compiler_accepts_flags(compiler, extra_flags):
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    build_dir = Path(tempfile.mkdtemp(prefix="probe-", dir=RUNTIME_ROOT))
    source_path = build_dir / "probe.cpp"
    binary_path = build_dir / "probe"
    source_path.write_text(
        "#include <vector>\nint main() { std::vector<int> v{1, 2}; return (int)v.size(); }\n",
        encoding="utf-8",
    )

    compile_cmd = [
        compiler,
        "-std=c++17",
        *extra_flags,
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
    return result.returncode == 0


def available_compiler_variants():
    variants = []
    seen = set()

    for compiler in find_compilers():
        compiler_kind = _compiler_kind(compiler)
        compiler_name = Path(compiler).name
        default_expected_abi = "libstdcxx" if compiler_kind == "gcc" else None
        candidate_variants = [
            CompilerVariant(
                name=f"{compiler_name}-default",
                compiler=compiler,
                expected_abi=default_expected_abi,
            )
        ]

        if compiler_kind == "clang":
            if _compiler_accepts_flags(compiler, ("-stdlib=libc++",)):
                candidate_variants.append(
                    CompilerVariant(
                        name=f"{compiler_name}-libcxx",
                        compiler=compiler,
                        extra_flags=("-stdlib=libc++",),
                        expected_abi="libcxx",
                    )
                )
            if _compiler_accepts_flags(compiler, ("-stdlib=libstdc++",)):
                candidate_variants.append(
                    CompilerVariant(
                        name=f"{compiler_name}-libstdcxx",
                        compiler=compiler,
                        extra_flags=("-stdlib=libstdc++",),
                        expected_abi="libstdcxx",
                    )
                )

        for variant in candidate_variants:
            key = (_compiler_version_text(variant.compiler), variant.extra_flags)
            if key in seen:
                continue
            seen.add(key)
            variants.append(variant)

    return variants


def build_fixture(fixture_name, compiler_variant=None):
    compiler = compiler_variant.compiler if compiler_variant else find_compiler()
    if not compiler:
        raise unittest.SkipTest("C++ compiler not available for LLDB integration tests.")

    extra_flags = list(compiler_variant.extra_flags) if compiler_variant else []
    source_path = FIXTURES_DIR / fixture_name
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    build_prefix = f"fixture-{compiler_variant.name}-" if compiler_variant else "fixture-"
    build_dir = Path(tempfile.mkdtemp(prefix=build_prefix, dir=RUNTIME_ROOT))
    binary_path = build_dir / source_path.stem

    compile_cmd = [
        compiler,
        "-std=c++17",
        "-g",
        "-O0",
        *extra_flags,
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


def classify_vector_abi_from_output(text):
    if "__begin_" in text or "__end_cap_" in text or "std::__1::vector" in text:
        return "libcxx"
    if "_M_impl" in text or "_M_start" in text or "_M_finish" in text:
        return "libstdcxx"
    return "unknown"


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
