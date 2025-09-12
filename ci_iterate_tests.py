#!/usr/bin/env python3

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple, Optional
import xml.etree.ElementTree as ET

REPO_ROOT = Path(__file__).parent
SOURCE_PATH = os.environ.get("SOURCE_PATH", "src/main/java")
TEST_PATH = os.environ.get("TEST_PATH", "src/test/java")
AGENT_TEST_SRC = REPO_ROOT / TEST_PATH
GUIDE_PATH = REPO_ROOT / "PROMPT_GUIDE.md"
GEN_SCRIPT = REPO_ROOT / "generate_tests.py"


def run(cmd: List[str], cwd: Path = REPO_ROOT, check: bool = True) -> Tuple[int, str]:
    proc = subprocess.run(cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stdout}")
    return proc.returncode, proc.stdout


def jacoco_xml_paths() -> List[Path]:
    # Look for test module reports first (they have the actual coverage data)
    test_modules = ["agent-tests", "copilot-tests"]  # agent-tests first as it has the actual coverage data
    for module in test_modules:
        module_path = REPO_ROOT / module / "target" / "site" / "jacoco" / "jacoco.xml"
        if module_path.exists():
            return [module_path]
    
    # Fallback to aggregated reports
    for module in test_modules:
        module_path = REPO_ROOT / module / "target" / "site" / "jacoco-aggregate" / "jacoco.xml"
        if module_path.exists():
            return [module_path]
    
    # Last resort: any jacoco.xml
    return list(REPO_ROOT.glob("**/target/site/jacoco*/jacoco.xml"))


def read_line_coverage() -> float:
    paths = jacoco_xml_paths()
    if not paths:
        return 0.0
    try:
        tree = ET.parse(paths[0])
        root = tree.getroot()
        
        # Look for the root-level LINE counter (the overall coverage)
        # It should be the last one in the document
        line_counters = []
        for counter in root.iter("counter"):
            if counter.attrib.get("type") == "LINE":
                line_counters.append(counter)
        
        if not line_counters:
            return 0.0
            
        # Use the last (root-level) LINE counter
        counter = line_counters[-1]
        missed = int(counter.attrib.get("missed", "0"))
        covered = int(counter.attrib.get("covered", "0"))
        total = missed + covered
        if total == 0:
            return 0.0
        return round(covered * 100.0 / total, 2)
    except Exception as e:
        print(f"Error reading coverage: {e}")
        return 0.0


def get_changed_java_files(base_sha: str, head_sha: str) -> List[Path]:
    code, out = run(["git", "diff", "--name-only", f"{base_sha}..{head_sha}"], check=False)
    files = [f.strip() for f in out.splitlines() if f.strip().endswith(".java")]
    # Only source files under configured source path
    keep = []
    for f in files:
        p = (REPO_ROOT / f).resolve()
        if SOURCE_PATH in str(p):
            keep.append(p)
    return keep


def get_all_java_files() -> List[Path]:
    """Get all Java source files in the configured source path."""
    source_dir = REPO_ROOT / SOURCE_PATH
    if not source_dir.exists():
        return []
    return list(source_dir.glob("**/*.java"))


def derive_test_path_from_source(java_source: Path) -> Path:
    # Mirror package path; name as ClassNameTest.java
    rel = java_source.parts[java_source.parts.index("java") + 1 :]
    class_name = java_source.stem + "Test"
    return AGENT_TEST_SRC.joinpath(*rel[:-1], class_name + ".java")


def generate_test_for(java_file: Path, out_path: Path) -> bool:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    code, out = run(
        [
            sys.executable,
            str(GEN_SCRIPT),
            "--guide",
            str(GUIDE_PATH),
            "--model",
            os.environ.get("GEN_MODEL", "gemini-1.5-pro"),
            "--java",
            str(java_file),
            "--out",
            str(out_path),
        ],
        check=False,
    )
    return code == 0


def run_project_tests() -> bool:
    code, _ = run(["mvn", "-q", "-DskipTests=false", "test"], check=False)
    return code == 0


def main() -> int:
    threshold = float(os.environ.get("COVERAGE_THRESHOLD", "80"))
    base_sha = os.environ.get("BASE_SHA") or os.environ.get("GITHUB_BASE_SHA") or os.environ.get("GITHUB_EVENT_BEFORE", "")
    head_sha = os.environ.get("HEAD_SHA") or os.environ.get("GITHUB_SHA", "")
    if not base_sha or not head_sha:
        sys.stderr.write("BASE_SHA or HEAD_SHA not set.\n")
        return 2

    # Initial test run to produce JaCoCo
    if not run_project_tests():
        # Let upstream step handle failures; we only improve coverage, not fix unit failures here
        sys.stderr.write("Initial mvn test failed; skipping coverage iteration.\n")
        return 0

    cov = read_line_coverage()
    if cov >= threshold:
        print(f"Coverage {cov}% >= {threshold}%. Nothing to do.")
        return 0

    # Get all Java files to improve coverage, not just changed ones
    all_java_files = get_all_java_files()
    if not all_java_files:
        print("No Java sources found; skipping coverage iteration.")
        return 0

    attempts = 0
    max_attempts = int(os.environ.get("MAX_COVERAGE_ATTEMPTS", "6"))
    for src in all_java_files:
        if attempts >= max_attempts:
            break
        test_path = derive_test_path_from_source(src)
        print(f"Generating test for coverage: {src} -> {test_path}")
        if not generate_test_for(src, test_path):
            print(f"Generation failed for {src}")
            continue
        # Verify whole project to catch regressions
        if not run_project_tests():
            print(f"New test caused failures; reverting {test_path}")
            try:
                test_path.unlink(missing_ok=True)
            except Exception:
                pass
            # Re-run to restore prior state
            run_project_tests()
            continue
        attempts += 1
        cov = read_line_coverage()
        print(f"Coverage after accept: {cov}%")
        if cov >= threshold:
            print(f"Reached coverage threshold {threshold}%.")
            return 0

    # Final status
    cov = read_line_coverage()
    print(f"Final coverage: {cov}% (threshold {threshold}%)")
    # Non-blocking: return 0; gating can be enforced in workflow conditionally
    return 0


if __name__ == "__main__":
    sys.exit(main())


