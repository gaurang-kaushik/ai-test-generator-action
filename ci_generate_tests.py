#!/usr/bin/env python3

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

REPO_ROOT = Path(__file__).parent
SOURCE_PATH = os.environ.get("SOURCE_PATH", "src/main/java")
TEST_PATH = os.environ.get("TEST_PATH", "src/test/java")
APP_SRC = REPO_ROOT / SOURCE_PATH
AGENT_TEST_SRC = REPO_ROOT / TEST_PATH
GUIDE_PATH = REPO_ROOT / "PROMPT_GUIDE.md"
GEN_SCRIPT = REPO_ROOT / "generate_tests.py"


def run(cmd: List[str], cwd: Path = REPO_ROOT, check: bool = True) -> Tuple[int, str]:
    proc = subprocess.run(cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stdout}")
    return proc.returncode, proc.stdout


def get_changed_java_files(base_sha: str, head_sha: str) -> List[Path]:
    # Try different git diff approaches to handle various scenarios
    try:
        # First try the standard range approach
        _code, out = run(["git", "diff", "--name-only", f"{base_sha}..{head_sha}"])
    except RuntimeError:
        try:
            # If range fails, try comparing with HEAD~1
            _code, out = run(["git", "diff", "--name-only", "HEAD~1", "HEAD"])
        except RuntimeError:
            try:
                # If that fails, try comparing with the previous commit
                _code, out = run(["git", "diff", "--name-only", "HEAD~1"])
            except RuntimeError:
                # Last resort: get all Java files in the source directory
                print("Warning: Could not determine changed files, processing all Java files")
                return list(APP_SRC.rglob("*.java"))
    
    files = [line.strip() for line in out.splitlines() if line.strip()]
    java_files = []
    for f in files:
        p = (REPO_ROOT / f).resolve()
        if p.suffix == ".java" and str(p).startswith(str(APP_SRC)):
            java_files.append(p)
    
    # LIMIT TO ONLY CHANGED FILES - Don't process entire repository
    if not java_files:
        print("No changed Java files found. Skipping test generation.")
        return []
    
    print(f"🎯 Found {len(java_files)} changed Java files - generating tests only for these")
    return java_files


def derive_test_path(java_file: Path) -> Path:
    rel = java_file.relative_to(APP_SRC)
    target = AGENT_TEST_SRC / rel
    name = target.stem + "Test" + target.suffix
    return target.with_name(name)


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def main() -> int:
    print("🔍 Starting ci_generate_tests.py...")
    
    base_sha = os.environ.get("BASE_SHA") or os.environ.get("GITHUB_BASE_SHA") or os.environ.get("GITHUB_EVENT_BEFORE", "")
    head_sha = os.environ.get("HEAD_SHA") or os.environ.get("GITHUB_SHA", "")
    print(f"📋 Git SHAs - BASE: {base_sha}, HEAD: {head_sha}")
    
    if not base_sha or not head_sha:
        sys.stderr.write("BASE_SHA or HEAD_SHA not set. Provide env vars or run inside GitHub Actions.\n")
        return 2

    if not GEN_SCRIPT.exists():
        sys.stderr.write(f"Missing generate_tests.py at {GEN_SCRIPT}\n")
        return 2
    if not GUIDE_PATH.exists():
        sys.stderr.write(f"Missing PROMPT_GUIDE.md at {GUIDE_PATH}\n")
        return 2

    print("🔍 Getting changed Java files...")
    changed = get_changed_java_files(base_sha, head_sha)
    print(f"📁 Found {len(changed)} changed Java files")
    
    if not changed:
        print("No Java changes under app/src/main/java. Skipping generation.")
        return 0

    failures = []
    for jf in changed:
        out_path = derive_test_path(jf)
        ensure_parent_dir(out_path)
        print(f"Generating test for {jf} -> {out_path}")
        code, out = run([
            sys.executable,
            str(GEN_SCRIPT),
            "--guide",
            str(GUIDE_PATH),
            "--model",
            os.environ.get("GEN_MODEL", "gemini-1.5-pro"),
            "--java",
            str(jf),
            "--out",
            str(out_path),
        ], check=False)
        if code != 0:
            failures.append((jf, out))
            # If generation fails, create a minimal compilable skeleton to keep CI green but visible
            skeleton = (
                "// NOTE: Generation failed in CI. Creating minimal skeleton test to keep CI running.\n"
                + "// See workflow logs for details.\n\n"
            )
            out_path.write_text(skeleton, encoding="utf-8")

    if failures:
        sys.stderr.write("Some files failed to generate tests:\n")
        for jf, log in failures:
            sys.stderr.write(f"- {jf}:\n{log}\n")
        # Non-fatal; allow CI to proceed to compile/tests to surface other issues
    return 0


if __name__ == "__main__":
    sys.exit(main())



