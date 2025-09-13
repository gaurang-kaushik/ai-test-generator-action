#!/usr/bin/env python3

import os
import subprocess
import sys
import time
import re
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


def run_maven_tests() -> Tuple[bool, str, List[str]]:
    """Run Maven tests and return (success, full_output, error_messages)"""
    print("🧪 Running Maven tests...")
    # Run Maven from the JtProject directory
    jtproject_dir = REPO_ROOT / "JtProject"
    code, output = run(["mvn", "test"], cwd=jtproject_dir, check=False)
    
    # Extract error messages from the output
    error_messages = []
    if code != 0:
        # Look for specific error patterns
        lines = output.split('\n')
        for i, line in enumerate(lines):
            if 'ERROR' in line or 'Exception' in line or 'Failed' in line:
                # Capture context around the error
                start = max(0, i-2)
                end = min(len(lines), i+3)
                error_context = '\n'.join(lines[start:end])
                error_messages.append(error_context)
    
    return code == 0, output, error_messages


def get_failing_test_files() -> List[Path]:
    """Get list of test files that are causing failures"""
    failing_tests = []
    test_dir = AGENT_TEST_SRC
    if test_dir.exists():
        for test_file in test_dir.glob("**/*Test.java"):
            failing_tests.append(test_file)
    return failing_tests


def generate_improved_test(java_file: Path, test_file: Path, error_messages: List[str]) -> bool:
    """Generate an improved test using error feedback"""
    print(f"🔧 Generating improved test for {java_file} based on errors...")
    
    # Read the original Java source
    try:
        with open(java_file, 'r') as f:
            java_code = f.read()
    except Exception as e:
        print(f"Error reading {java_file}: {e}")
        return False
    
    # Read the failing test if it exists
    failing_test_code = ""
    if test_file.exists():
        try:
            with open(test_file, 'r') as f:
                failing_test_code = f.read()
        except Exception as e:
            print(f"Error reading {test_file}: {e}")
    
    # Create an enhanced prompt with error feedback
    error_feedback = "\n".join(error_messages) if error_messages else "No specific errors captured"
    
    enhanced_prompt = f"""
CRITICAL: The previous test generation failed with these specific errors:
{error_feedback}

MOST IMPORTANT FIXES NEEDED:
1. CONSTRUCTOR ERRORS: Use NO-ARGS constructor + setters for JPA entities
   - WRONG: new Category(1, "name")
   - CORRECT: new Category(); category.setId(1); category.setName("name")
2. METHOD NAMES: Use EXACT camelCase method names from the actual class
3. TYPE SAFETY: Use EXACT types (int, not long; String, not Object)
4. IMPORTS: Include ALL necessary imports
5. MOCKITO: Use proper mocking patterns for Spring Boot
6. DATABASE MOCKING: For Spring Boot Application tests, use @MockBean to mock database connections
7. NO REAL DATABASE: Never let tests connect to real databases - always mock database dependencies

Original Java code:
{java_code}

Previous failing test (if any):
{failing_test_code}

Generate a corrected test that will compile without ANY errors. Focus on fixing the constructor and method name issues first, and ensure database connections are properly mocked.
"""
    
    # Write enhanced prompt to a temporary file
    temp_prompt_file = REPO_ROOT / "temp_enhanced_prompt.txt"
    with open(temp_prompt_file, 'w') as f:
        f.write(enhanced_prompt)
    
    try:
        # Generate improved test
        code, out = run([
            sys.executable,
            str(GEN_SCRIPT),
            "--guide", str(GUIDE_PATH),
            "--model", os.environ.get("MODEL", "gemini-2.0-flash-exp"),
            "--java", str(java_file),
            "--out", str(test_file),
        ], check=False)
        
        # Clean up temp file
        temp_prompt_file.unlink(missing_ok=True)
        
        return code == 0
    except Exception as e:
        print(f"Error generating improved test: {e}")
        temp_prompt_file.unlink(missing_ok=True)
        return False


def jacoco_xml_paths() -> List[Path]:
    """Find JaCoCo XML reports"""
    # Look for test module reports first
    test_modules = ["agent-tests", "copilot-tests"]
    for module in test_modules:
        module_path = REPO_ROOT / module / "target" / "site" / "jacoco" / "jacoco.xml"
        if module_path.exists():
            return [module_path]
    
    # Fallback to any jacoco.xml
    return list(REPO_ROOT.glob("**/target/site/jacoco*/jacoco.xml"))


def read_line_coverage() -> float:
    """Read line coverage from JaCoCo XML"""
    paths = jacoco_xml_paths()
    if not paths:
        return 0.0
    try:
        tree = ET.parse(paths[0])
        root = tree.getroot()
        
        line_counters = []
        for counter in root.iter("counter"):
            if counter.attrib.get("type") == "LINE":
                line_counters.append(counter)
        
        if not line_counters:
            return 0.0
            
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


def get_all_java_files() -> List[Path]:
    """Get only changed Java source files - NO FALLBACK to all files"""
    # Only process changed files, not entire repository
    base_sha = os.environ.get("BASE_SHA") or os.environ.get("GITHUB_BASE_SHA") or os.environ.get("GITHUB_EVENT_BEFORE", "")
    head_sha = os.environ.get("HEAD_SHA") or os.environ.get("GITHUB_SHA", "")
    
    if base_sha and head_sha:
        # Use git diff to get only changed files
        try:
            _code, out = run(["git", "diff", "--name-only", f"{base_sha}..{head_sha}"])
            files = [line.strip() for line in out.splitlines() if line.strip()]
            java_files = []
            for f in files:
                p = (REPO_ROOT / f).resolve()
                if p.suffix == ".java" and str(p).startswith(str(REPO_ROOT / SOURCE_PATH)):
                    java_files.append(p)
            print(f"🎯 Error iteration focusing on {len(java_files)} changed files only")
            return java_files
        except RuntimeError as e:
            print(f"❌ Git diff failed: {base_sha}..{head_sha} - {e}")
            try:
                # Try HEAD~1..HEAD as fallback (should work with fetch-depth: 0)
                _code, out = run(["git", "diff", "--name-only", "HEAD~1", "HEAD"])
                files = [line.strip() for line in out.splitlines() if line.strip()]
                java_files = []
                for f in files:
                    p = (REPO_ROOT / f).resolve()
                    if p.suffix == ".java" and str(p).startswith(str(REPO_ROOT / SOURCE_PATH)):
                        java_files.append(p)
                print(f"🎯 Error iteration focusing on {len(java_files)} changed files only (fallback)")
                return java_files
            except RuntimeError as e2:
                print(f"❌ All git diff attempts failed in error iteration: {e2}")
                print("🚫 CRITICAL: Cannot determine changed files - ABORTING to prevent processing all files")
                return []
    
    # If no git SHAs available, return empty list instead of processing all files
    print("❌ No git SHAs available - cannot determine changed files")
    print("🚫 ABORTING to prevent processing all files")
    return []


def derive_test_path_from_source(java_source: Path) -> Path:
    """Derive test file path from source file"""
    rel = java_source.parts[java_source.parts.index("java") + 1 :]
    class_name = java_source.stem + "Test"
    return AGENT_TEST_SRC.joinpath(*rel[:-1], class_name + ".java")


def main() -> int:
    print("🔄 Starting error-driven test improvement...")
    
    threshold = float(os.environ.get("COVERAGE_THRESHOLD", "80"))
    max_iterations = int(os.environ.get("MAX_ITERATIONS", "5"))
    
    # Ensure test directory exists
    AGENT_TEST_SRC.mkdir(parents=True, exist_ok=True)
    
    # Get all Java source files
    all_java_files = get_all_java_files()
    if not all_java_files:
        print("No Java sources found.")
        return 0
    
    print(f"Found {len(all_java_files)} Java source files")
    
    iteration = 0
    while iteration < max_iterations:
        iteration += 1
        print(f"\n🔄 Iteration {iteration}/{max_iterations}")
        
        # Run tests to see current state
        success, output, error_messages = run_maven_tests()
        
        if success:
            print("✅ All tests passing!")
            # Check coverage
            coverage = read_line_coverage()
            print(f"📊 Current coverage: {coverage}%")
            if coverage >= threshold:
                print(f"🎉 Coverage target {threshold}% reached!")
                return 0
        else:
            print(f"❌ Tests failing with {len(error_messages)} error(s)")
            print("🔍 Error details:")
            for i, error in enumerate(error_messages[:3]):  # Show first 3 errors
                print(f"  Error {i+1}: {error[:200]}...")
        
        # Generate or improve tests for each source file
        improved_any = False
        for java_file in all_java_files:
            test_file = derive_test_path_from_source(java_file)
            print(f"📝 Processing {java_file.name} -> {test_file.name}")
            
            # Generate improved test with error feedback
            if generate_improved_test(java_file, test_file, error_messages):
                print(f"✅ Generated improved test for {java_file.name}")
                improved_any = True
            else:
                print(f"❌ Failed to generate test for {java_file.name}")
        
        if not improved_any:
            print("❌ No tests could be improved this iteration")
            break
    
    # Final status
    success, _, _ = run_maven_tests()
    coverage = read_line_coverage()
    
    print(f"\n📊 Final Results:")
    print(f"  Tests passing: {'✅' if success else '❌'}")
    print(f"  Coverage: {coverage}% (target: {threshold}%)")
    
    if not success:
        print("❌ Some tests still failing after error-driven iteration")
        return 1
    elif coverage < threshold:
        print(f"⚠️ Coverage {coverage}% below threshold {threshold}%")
        return 1
    else:
        print("🎉 All tests passing and coverage target met!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
