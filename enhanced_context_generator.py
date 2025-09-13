#!/usr/bin/env python3

import os
import re
import ast
from pathlib import Path
from typing import List, Dict, Set, Optional
import subprocess

class JavaContextAnalyzer:
    def __init__(self, source_path: str):
        self.source_path = Path(source_path)
        self.context_cache = {}
    
    def analyze_java_file(self, file_path: Path) -> Dict:
        """Analyze a Java file and extract comprehensive context"""
        if file_path in self.context_cache:
            return self.context_cache[file_path]
        
        try:
            content = file_path.read_text(encoding='utf-8')
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return {}
        
        context = {
            'package': self._extract_package(content),
            'imports': self._extract_imports(content),
            'class_name': self._extract_class_name(content),
            'extends': self._extract_extends(content),
            'implements': self._extract_implements(content),
            'annotations': self._extract_annotations(content),
            'fields': self._extract_fields(content),
            'constructors': self._extract_constructors(content),
            'methods': self._extract_methods(content),
            'dependencies': self._extract_dependencies(content),
            'spring_annotations': self._extract_spring_annotations(content),
            'model_classes': self._find_model_classes(content),
        }
        
        self.context_cache[file_path] = context
        return context
    
    def _extract_package(self, content: str) -> str:
        match = re.search(r'package\s+([\w.]+);', content)
        return match.group(1) if match else ""
    
    def _extract_imports(self, content: str) -> List[str]:
        imports = re.findall(r'import\s+([\w.*]+);', content)
        return imports
    
    def _extract_class_name(self, content: str) -> str:
        match = re.search(r'(?:public\s+)?(?:class|interface|enum)\s+(\w+)', content)
        return match.group(1) if match else ""
    
    def _extract_extends(self, content: str) -> str:
        match = re.search(r'extends\s+([\w.]+)', content)
        return match.group(1) if match else ""
    
    def _extract_implements(self, content: str) -> List[str]:
        match = re.search(r'implements\s+([^{]+)', content)
        if match:
            return [imp.strip() for imp in match.group(1).split(',')]
        return []
    
    def _extract_annotations(self, content: str) -> List[str]:
        annotations = re.findall(r'@(\w+(?:\.\w+)*)', content)
        return annotations
    
    def _extract_fields(self, content: str) -> List[Dict]:
        fields = []
        # Match field declarations
        field_pattern = r'(?:@\w+(?:\([^)]*\))?\s*)*\s*(?:public|private|protected)?\s*(?:static\s+)?(?:final\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)(?:\s*=\s*[^;]+)?;'
        for match in re.finditer(field_pattern, content):
            fields.append({
                'type': match.group(1),
                'name': match.group(2)
            })
        return fields
    
    def _extract_constructors(self, content: str) -> List[Dict]:
        constructors = []
        # Match constructor declarations
        constructor_pattern = r'(?:public\s+)?(\w+)\s*\(([^)]*)\)\s*\{'
        for match in re.finditer(constructor_pattern, content):
            params = []
            if match.group(2).strip():
                for param in match.group(2).split(','):
                    param = param.strip()
                    if param:
                        parts = param.split()
                        if len(parts) >= 2:
                            params.append({
                                'type': parts[0],
                                'name': parts[1]
                            })
            constructors.append({
                'name': match.group(1),
                'parameters': params
            })
        return constructors
    
    def _extract_methods(self, content: str) -> List[Dict]:
        methods = []
        # Match method declarations
        method_pattern = r'(?:@\w+(?:\([^)]*\))?\s*)*\s*(?:public|private|protected)?\s*(?:static\s+)?(?:final\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)\s*\(([^)]*)\)\s*(?:throws\s+[\w\s,]+)?\s*\{'
        for match in re.finditer(method_pattern, content):
            params = []
            if match.group(3).strip():
                for param in match.group(3).split(','):
                    param = param.strip()
                    if param:
                        parts = param.split()
                        if len(parts) >= 2:
                            params.append({
                                'type': parts[0],
                                'name': parts[1]
                            })
            methods.append({
                'return_type': match.group(1),
                'name': match.group(2),
                'parameters': params
            })
        return methods
    
    def _extract_dependencies(self, content: str) -> List[str]:
        dependencies = []
        # Look for @Autowired, @Mock, @InjectMocks, etc.
        autowired_pattern = r'@Autowired\s+(?:public\s+)?(?:static\s+)?(?:final\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)'
        for match in re.finditer(autowired_pattern, content):
            dependencies.append({
                'type': match.group(1),
                'name': match.group(2),
                'annotation': 'Autowired'
            })
        return dependencies
    
    def _extract_spring_annotations(self, content: str) -> List[str]:
        spring_annotations = []
        spring_patterns = [
            r'@Service', r'@Repository', r'@Controller', r'@RestController',
            r'@Component', r'@Configuration', r'@Entity', r'@Table'
        ]
        for pattern in spring_patterns:
            if re.search(pattern, content):
                spring_annotations.append(pattern[1:])  # Remove @
        return spring_annotations
    
    def _find_model_classes(self, content: str) -> List[str]:
        # Look for model/entity classes in the same package
        model_classes = []
        package = self._extract_package(content)
        if package:
            models_dir = self.source_path / package.replace('.', '/') / 'models'
            if models_dir.exists():
                for model_file in models_dir.glob('*.java'):
                    model_content = model_file.read_text(encoding='utf-8')
                    class_name = self._extract_class_name(model_content)
                    if class_name:
                        model_classes.append(class_name)
        return model_classes
    
    def generate_comprehensive_context(self, java_file: Path) -> str:
        """Generate comprehensive context for AI test generation"""
        context = self.analyze_java_file(java_file)
        
        context_text = f"""
COMPREHENSIVE JAVA CONTEXT FOR TEST GENERATION
==============================================

TARGET FILE: {java_file.name}
PACKAGE: {context.get('package', 'N/A')}
CLASS NAME: {context.get('class_name', 'N/A')}

INHERITANCE:
- Extends: {context.get('extends', 'None')}
- Implements: {', '.join(context.get('implements', []))}

ANNOTATIONS:
- Class Annotations: {', '.join(context.get('annotations', []))}
- Spring Annotations: {', '.join(context.get('spring_annotations', []))}

CONSTRUCTORS:
"""
        
        for constructor in context.get('constructors', []):
            params = ', '.join([f"{p['type']} {p['name']}" for p in constructor['parameters']])
            context_text += f"- {constructor['name']}({params})\n"
        
        context_text += f"""
FIELDS:
"""
        for field in context.get('fields', []):
            context_text += f"- {field['type']} {field['name']}\n"
        
        context_text += f"""
METHODS:
"""
        for method in context.get('methods', []):
            params = ', '.join([f"{p['type']} {p['name']}" for p in method['parameters']])
            context_text += f"- {method['return_type']} {method['name']}({params})\n"
        
        context_text += f"""
DEPENDENCIES (for mocking):
"""
        for dep in context.get('dependencies', []):
            context_text += f"- {dep['annotation']} {dep['type']} {dep['name']}\n"
        
        context_text += f"""
IMPORTS (for reference):
"""
        for imp in context.get('imports', []):
            context_text += f"- {imp}\n"
        
        context_text += f"""
MODEL CLASSES (for test data creation):
"""
        for model in context.get('model_classes', []):
            context_text += f"- {model}\n"
        
        context_text += f"""
TEST GENERATION GUIDELINES:
1. Use correct constructor calls based on the constructors listed above
2. Mock all dependencies listed in the DEPENDENCIES section
3. Use appropriate Spring annotations (@Service, @Repository, etc.)
4. Import all necessary classes from the IMPORTS section
5. Create test data using the MODEL CLASSES listed above
6. Follow JUnit5 + Mockito patterns
7. Ensure all method calls match the exact signatures listed above
"""
        
        return context_text

def main():
    if len(os.sys.argv) != 3:
        print("Usage: python enhanced_context_generator.py <java_file> <output_file>")
        sys.exit(1)
    
    java_file = Path(os.sys.argv[1])
    output_file = Path(os.sys.argv[2])
    
    analyzer = JavaContextAnalyzer("JtProject/src/main/java")
    context = analyzer.generate_comprehensive_context(java_file)
    
    output_file.write_text(context, encoding='utf-8')
    print(f"Generated comprehensive context for {java_file.name}")

if __name__ == "__main__":
    main()
