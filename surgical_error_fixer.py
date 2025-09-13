#!/usr/bin/env python3

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional

class SurgicalErrorFixer:
    def __init__(self, source_path: str, test_path: str):
        self.source_path = Path(source_path)
        self.test_path = Path(test_path)
        self.error_patterns = {
            'constructor_error': r'constructor (\w+) in class [\w.]+ cannot be applied to given types;\s*required: no arguments\s*found: ([^;]+)',
            'method_not_found': r'cannot find symbol\s*symbol:\s*method (\w+)\([^)]*\)\s*location: variable (\w+) of type ([\w.]+)',
            'type_conversion': r'incompatible types: ([^;]+)',
            'missing_import': r'cannot find symbol\s*symbol:\s*class (\w+)',
            'class_name_mismatch': r'class (\w+) is public, should be declared in a file named (\w+)\.java',
            'private_access': r'(\w+) has private access in ([\w.]+)',
            'serializable_error': r'no suitable method found for thenReturn\(([\w.]+)\)'
        }
    
    def analyze_compilation_errors(self, error_output: str) -> List[Dict]:
        """Analyze compilation errors and extract specific issues"""
        errors = []
        lines = error_output.split('\n')
        
        for i, line in enumerate(lines):
            if 'Error:' in line and 'cannot find symbol' in line:
                # Look ahead for the symbol details
                if i + 1 < len(lines) and 'symbol:' in lines[i + 1]:
                    error_info = self._extract_symbol_error(line, lines[i + 1])
                    if error_info:
                        errors.append(error_info)
            
            elif 'constructor' in line and 'cannot be applied' in line:
                error_info = self._extract_constructor_error(line)
                if error_info:
                    errors.append(error_info)
            
            elif 'incompatible types' in line:
                error_info = self._extract_type_error(line)
                if error_info:
                    errors.append(error_info)
            
            elif 'class' in line and 'is public, should be declared' in line:
                error_info = self._extract_class_name_error(line)
                if error_info:
                    errors.append(error_info)
        
        return errors
    
    def _extract_symbol_error(self, error_line: str, symbol_line: str) -> Optional[Dict]:
        """Extract method not found errors"""
        # Extract file path and line number
        file_match = re.search(r'([^:]+):(\d+):(\d+)', error_line)
        if not file_match:
            return None
        
        file_path = file_match.group(1)
        line_num = int(file_match.group(2))
        
        # Extract method name and class
        method_match = re.search(r'method (\w+)\([^)]*\)', symbol_line)
        class_match = re.search(r'variable (\w+) of type ([\w.]+)', symbol_line)
        
        if method_match and class_match:
            return {
                'type': 'method_not_found',
                'file': file_path,
                'line': line_num,
                'method': method_match.group(1),
                'variable': class_match.group(1),
                'class_type': class_match.group(2)
            }
        return None
    
    def _extract_constructor_error(self, line: str) -> Optional[Dict]:
        """Extract constructor errors"""
        file_match = re.search(r'([^:]+):(\d+):(\d+)', line)
        if not file_match:
            return None
        
        constructor_match = re.search(r'constructor (\w+) in class ([\w.]+) cannot be applied to given types;\s*required: no arguments\s*found: ([^;]+)', line)
        if constructor_match:
            return {
                'type': 'constructor_error',
                'file': file_match.group(1),
                'line': int(file_match.group(2)),
                'class_name': constructor_match.group(1),
                'full_class': constructor_match.group(2),
                'provided_args': constructor_match.group(3).strip()
            }
        return None
    
    def _extract_type_error(self, line: str) -> Optional[Dict]:
        """Extract type conversion errors"""
        file_match = re.search(r'([^:]+):(\d+):(\d+)', line)
        if not file_match:
            return None
        
        type_match = re.search(r'incompatible types: ([^;]+)', line)
        if type_match:
            return {
                'type': 'type_conversion',
                'file': file_match.group(1),
                'line': int(file_match.group(2)),
                'conversion': type_match.group(1).strip()
            }
        return None
    
    def _extract_class_name_error(self, line: str) -> Optional[Dict]:
        """Extract class name mismatch errors"""
        file_match = re.search(r'([^:]+):(\d+):(\d+)', line)
        if not file_match:
            return None
        
        class_match = re.search(r'class (\w+) is public, should be declared in a file named (\w+)\.java', line)
        if class_match:
            return {
                'type': 'class_name_mismatch',
                'file': file_match.group(1),
                'line': int(file_match.group(2)),
                'actual_class': class_match.group(1),
                'expected_class': class_match.group(2)
            }
        return None
    
    def get_targeted_context(self, java_file: Path, error_info: Dict) -> str:
        """Get targeted context for a specific error"""
        try:
            content = java_file.read_text(encoding='utf-8')
        except:
            return ""
        
        # Extract the specific method/class around the error
        lines = content.split('\n')
        error_line = error_info.get('line', 0)
        
        # Get context around the error (5 lines before and after)
        start_line = max(0, error_line - 6)
        end_line = min(len(lines), error_line + 5)
        context_lines = lines[start_line:end_line]
        
        context = f"""
TARGETED ERROR CONTEXT
=====================
File: {java_file.name}
Error Type: {error_info['type']}
Error Line: {error_line}

RELEVANT CODE CONTEXT:
"""
        for i, line in enumerate(context_lines, start_line + 1):
            marker = ">>> " if i == error_line else "    "
            context += f"{marker}{i:3d}: {line}\n"
        
        # Add specific guidance based on error type
        if error_info['type'] == 'constructor_error':
            context += f"""
CONSTRUCTOR FIX GUIDANCE:
- Class {error_info['class_name']} requires no-argument constructor
- Use: new {error_info['class_name']}()
- Then set properties using setters
- Provided args: {error_info['provided_args']}
"""
        elif error_info['type'] == 'method_not_found':
            context += f"""
METHOD FIX GUIDANCE:
- Method {error_info['method']} does not exist on {error_info['class_type']}
- Check correct method name (camelCase)
- Common setters: setCartId(), setCategoryId(), setProductId()
- Common getters: getCartId(), getCategoryId(), getProductId()
"""
        elif error_info['type'] == 'type_conversion':
            context += f"""
TYPE CONVERSION FIX GUIDANCE:
- Issue: {error_info['conversion']}
- Use explicit casting: (int) longValue
- Or use correct type: Long instead of Integer
"""
        elif error_info['type'] == 'class_name_mismatch':
            context += f"""
CLASS NAME FIX GUIDANCE:
- Class name: {error_info['actual_class']}
- Expected: {error_info['expected_class']}
- Fix: Rename class to match filename
"""
        
        return context
    
    def generate_surgical_fix(self, java_file: Path, test_file: Path, error_info: Dict) -> str:
        """Generate a surgical fix for a specific error"""
        context = self.get_targeted_context(java_file, error_info)
        
        # Read the current test file
        try:
            test_content = test_file.read_text(encoding='utf-8')
        except:
            test_content = ""
        
        # Create a focused prompt for this specific error
        prompt = f"""
SURGICAL TEST FIX
================

You need to fix a SPECIFIC compilation error in a test file.

{context}

CURRENT TEST FILE:
{test_content}

INSTRUCTIONS:
1. Fix ONLY the specific error mentioned above
2. Do NOT rewrite the entire file
3. Make minimal changes to fix the compilation error
4. Preserve all other working code
5. Use the guidance provided above

OUTPUT: Provide ONLY the corrected lines or method that fixes the error.
"""
        
        return prompt

def main():
    if len(sys.argv) != 4:
        print("Usage: python surgical_error_fixer.py <java_file> <test_file> <error_output>")
        sys.exit(1)
    
    java_file = Path(sys.argv[1])
    test_file = Path(sys.argv[2])
    error_output = sys.argv[3]
    
    fixer = SurgicalErrorFixer("JtProject/src/main/java", "JtProject/src/test/java")
    errors = fixer.analyze_compilation_errors(error_output)
    
    print(f"Found {len(errors)} specific errors:")
    for error in errors:
        print(f"- {error['type']} in {error['file']} at line {error['line']}")
        
        # Generate surgical fix for this specific error
        fix_prompt = fixer.generate_surgical_fix(java_file, test_file, error)
        print(f"\nSURGICAL FIX PROMPT:\n{fix_prompt}\n")

if __name__ == "__main__":
    main()
