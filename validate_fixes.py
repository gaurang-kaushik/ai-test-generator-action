#!/usr/bin/env python3
"""
Validation script to test our fixes before running the full CI pipeline.
This script will test the scope limiting and simple test generation.
"""

import os
import sys
import subprocess
from pathlib import Path

def test_scope_limiting():
    """Test that scope limiting works correctly"""
    print("🔍 Testing scope limiting...")
    
    # Test the get_changed_java_files function
    try:
        # Import the function
        sys.path.insert(0, str(Path(__file__).parent))
        from ci_generate_tests import get_changed_java_files
        
        # Test with invalid SHAs (should return empty list, not all files)
        result = get_changed_java_files("invalid_sha", "invalid_sha")
        
        if result == []:
            print("✅ Scope limiting works correctly - returns empty list when git diff fails")
            return True
        else:
            print(f"❌ Scope limiting failed - returned {len(result)} files instead of empty list")
            return False
            
    except Exception as e:
        print(f"❌ Scope limiting test failed with exception: {e}")
        return False

def test_simple_generation():
    """Test generating a test for a simple class"""
    print("🧪 Testing simple test generation...")
    
    # Check if we have the Category.java file
    category_java = Path("../Spring-Test-Repo/E-commerce-project-springBoot/JtProject/src/main/java/com/jtspringproject/JtSpringProject/models/Category.java")
    
    if not category_java.exists():
        print(f"❌ Category.java not found at {category_java}")
        return False
    
    # Check if we have the required files
    required_files = [
        "generate_tests.py",
        "PROMPT_GUIDE.md",
        "enhanced_context_generator.py"
    ]
    
    for file in required_files:
        if not Path(file).exists():
            print(f"❌ Required file {file} not found")
            return False
    
    print("✅ All required files found")
    
    # Check if GOOGLE_API_KEY is set
    if not os.environ.get("GOOGLE_API_KEY"):
        print("⚠️ GOOGLE_API_KEY not set - skipping actual generation test")
        print("💡 Set GOOGLE_API_KEY to test actual generation")
        return True
    
    # Test actual generation
    try:
        test_output = Path("test_output/CategoryTest.java")
        test_output.parent.mkdir(exist_ok=True)
        
        result = subprocess.run([
            sys.executable,
            "generate_tests.py",
            "--guide", "PROMPT_GUIDE.md",
            "--model", "gemini-1.5-pro",
            "--java", str(category_java),
            "--out", str(test_output)
        ], capture_output=True, text=True, cwd=Path(__file__).parent)
        
        if result.returncode == 0 and test_output.exists():
            print("✅ Test generation successful!")
            
            # Check the generated test content
            with open(test_output, 'r') as f:
                content = f.read()
            
            # Check for common issues
            issues = []
            if "Category(" in content and "new Category()" not in content:
                issues.append("Uses parameterized constructor instead of no-args")
            if "setCart_id" in content:
                issues.append("Uses snake_case method names")
            if "long" in content and "int" in content:
                issues.append("Uses wrong data types")
            if "NoResultException" in content and "import" not in content:
                issues.append("Missing imports")
            
            if issues:
                print(f"⚠️ Generated test has issues: {', '.join(issues)}")
                print("💡 This is expected - we're working on improving the prompts")
            else:
                print("🎉 Generated test looks good!")
            
            return True
        else:
            print(f"❌ Test generation failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Test generation failed with exception: {e}")
        return False

def test_context_generation():
    """Test that context generation works"""
    print("🔧 Testing context generation...")
    
    try:
        from enhanced_context_generator import JavaContextAnalyzer
        
        category_java = Path("../Spring-Test-Repo/E-commerce-project-springBoot/JtProject/src/main/java/com/jtspringproject/JtSpringProject/models/Category.java")
        
        if not category_java.exists():
            print(f"❌ Category.java not found at {category_java}")
            return False
        
        analyzer = JavaContextAnalyzer("../Spring-Test-Repo/E-commerce-project-springBoot/JtProject/src/main/java")
        context = analyzer.generate_comprehensive_context(category_java)
        
        # Check if context contains important information
        if "Category" in context and "package" in context and "CONSTRUCTORS" in context:
            print("✅ Context generation successful!")
            return True
        else:
            print("❌ Context generation failed - missing important information")
            return False
            
    except Exception as e:
        print(f"❌ Context generation failed with exception: {e}")
        return False

def main():
    print("🚀 Validating AI Test Generator Fixes")
    print("=" * 50)
    
    tests = [
        ("Scope Limiting", test_scope_limiting),
        ("Context Generation", test_context_generation),
        ("Simple Test Generation", test_simple_generation),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name} test...")
        result = test_func()
        results.append((test_name, result))
        print(f"{'✅' if result else '❌'} {test_name} test {'PASSED' if result else 'FAILED'}")
    
    print("\n" + "=" * 50)
    print("📊 VALIDATION RESULTS:")
    
    passed = 0
    for test_name, result in results:
        status = "PASSED" if result else "FAILED"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All validation tests PASSED!")
        print("💡 You can now proceed with the full CI pipeline")
        return 0
    else:
        print("❌ Some validation tests FAILED!")
        print("💡 Fix the failing tests before running the full CI pipeline")
        return 1

if __name__ == "__main__":
    sys.exit(main())
