#!/usr/bin/env python3
"""
Simple test script to verify the AI test generation works for one file.
This will help us validate our fixes before running the full CI pipeline.
"""

import os
import sys
import subprocess
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

def test_simple_generation():
    """Test generating a test for the simple Category.java class"""
    print("🧪 Testing simple test generation for Category.java")
    
    # Path to the Category.java file
    category_java = Path("Spring-Test-Repo/E-commerce-project-springBoot/JtProject/src/main/java/com/jtspringproject/JtSpringProject/models/Category.java")
    
    if not category_java.exists():
        print(f"❌ Category.java not found at {category_java}")
        return False
    
    # Output path for the generated test
    test_output = Path("test_output/CategoryTest.java")
    test_output.parent.mkdir(exist_ok=True)
    
    # Set up environment variables
    os.environ["GOOGLE_API_KEY"] = os.environ.get("GOOGLE_API_KEY", "")
    os.environ["GEN_MODEL"] = "gemini-1.5-pro"
    
    if not os.environ.get("GOOGLE_API_KEY"):
        print("❌ GOOGLE_API_KEY not set. Please set it to test generation.")
        return False
    
    try:
        # Run the test generation
        print(f"📝 Generating test for {category_java}")
        result = subprocess.run([
            sys.executable,
            "generate_tests.py",
            "--guide", "PROMPT_GUIDE.md",
            "--model", "gemini-1.5-pro",
            "--java", str(category_java),
            "--out", str(test_output)
        ], capture_output=True, text=True, cwd=Path(__file__).parent)
        
        if result.returncode == 0:
            print(f"✅ Test generation successful!")
            print(f"📄 Generated test saved to: {test_output}")
            
            # Read and display the generated test
            if test_output.exists():
                with open(test_output, 'r') as f:
                    content = f.read()
                print(f"\n📋 Generated test content:\n{'-'*50}")
                print(content)
                print(f"{'-'*50}")
                return True
            else:
                print("❌ Test file was not created")
                return False
        else:
            print(f"❌ Test generation failed with return code {result.returncode}")
            print(f"Error output: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Exception during test generation: {e}")
        return False

def main():
    print("🚀 Starting simple test generation validation")
    print("=" * 60)
    
    success = test_simple_generation()
    
    print("=" * 60)
    if success:
        print("🎉 Simple test generation validation PASSED!")
        print("💡 You can now proceed with the full CI pipeline")
    else:
        print("❌ Simple test generation validation FAILED!")
        print("💡 Fix the issues before running the full CI pipeline")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
