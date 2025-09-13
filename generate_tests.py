#!/usr/bin/env python3

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Optional

try:
    import google.generativeai as genai
except ImportError:
    genai = None  # We'll give a helpful error if missing


SECTION_SYSTEM_HEADING = "🧠 System Prompt for the Agent"
SECTION_USER_TEMPLATE_HEADING = "📝 User Prompt Template"
SECTION_SEPARATOR = "⸻"


def read_text_file(path: str) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def extract_system_prompt(guide_text: str) -> str:
    # Find the system section anchor
    sys_idx = guide_text.find(SECTION_SYSTEM_HEADING)
    if sys_idx == -1:
        # Fallback: directly search for the known first line of the system prompt
        m = re.search(r"^You are an expert Java developer and test automation engineer\..*", guide_text, re.M | re.S)
        if not m:
            raise ValueError("Could not locate the System Prompt section in PROMPT_GUIDE.md")
        start = m.start()
    else:
        # From the heading, locate the line that starts the actual prompt ("You are an expert ...")
        after_heading = guide_text[sys_idx:]
        m = re.search(r"You are an expert Java developer and test automation engineer\..*", after_heading, re.S)
        if not m:
            raise ValueError("System Prompt heading found but prompt body not detected.")
        start = sys_idx + m.start()

    # Determine the end boundary: next section heading or separator
    candidates = []
    for marker in (SECTION_USER_TEMPLATE_HEADING, SECTION_SEPARATOR, "🚀 3-Day Build Plan", "💡 Usage in Cursor"):
        idx = guide_text.find(marker, start + 1)
        if idx != -1:
            candidates.append(idx)
    end = min(candidates) if candidates else len(guide_text)

    system_prompt = guide_text[start:end].strip()

    # Ensure the prompt begins with the expected opening sentence for clarity
    if not system_prompt.startswith("You are an expert Java developer"):
        # Try to trim leading lines before that sentence
        m2 = re.search(r"You are an expert Java developer and test automation engineer\..*", system_prompt, re.S)
        if m2:
            system_prompt = system_prompt[m2.start():].strip()

    if not system_prompt:
        raise ValueError("Extracted system prompt is empty.")
    return system_prompt


def build_user_prompt(java_code: str, context_file: str = None) -> str:
    # Mirrors the User Prompt Template in PROMPT_GUIDE.md
    context_section = ""
    if context_file and os.path.exists(context_file):
        with open(context_file, 'r', encoding='utf-8') as f:
            context_section = f"\n\nENHANCED CONTEXT:\n{f.read()}\n"
    
    return (
        "Generate a JUnit5 + Mockito test class for the following Java code. "
        "Follow the system instructions provided.\n\n"
        "Java code:\n"
        f"{java_code}\n"
        f"{context_section}"
        "END.\n\n"
        "CRITICAL REQUIREMENTS - READ CAREFULLY:\n"
        "1. CONSTRUCTOR USAGE: Use NO-ARGS constructor + setters for JPA entities. Do NOT use parameterized constructors unless explicitly shown in the ENHANCED CONTEXT.\n"
        "   - WRONG: new Category(1, \"name\")\n"
        "   - CORRECT: new Category(); category.setId(1); category.setName(\"name\")\n"
        "2. METHOD NAMES: Use EXACT method names from the ENHANCED CONTEXT - follow camelCase convention (e.g., setCartId, not setCart_id).\n"
        "3. TYPE SAFETY: Use EXACT types from the ENHANCED CONTEXT - no type conversions (e.g., use int, not long).\n"
        "   - CRITICAL: Check field types in the ENHANCED CONTEXT before setting values\n"
        "   - If field is 'private int price', use setPrice(10) NOT setPrice(10.0)\n"
        "   - If field is 'private double price', use setPrice(10.0) NOT setPrice(10)\n"
        "   - If field is 'private String name', use setName(\"value\") NOT setName(123)\n"
        "4. IMPORTS: Include ALL necessary imports - check the IMPORTS section in ENHANCED CONTEXT.\n"
        "5. MOCKITO: For Mockito.thenReturn(), ensure return types are Serializable or use proper mocking patterns.\n"
        "6. SPRING BOOT: Use @ExtendWith(MockitoExtension.class) for unit tests, NOT @SpringBootTest.\n"
        "7. JPA ENTITIES: For @Entity classes, use no-args constructor + setters pattern.\n"
        "8. MOCKING: Mock all @Autowired, @Repository, @Service dependencies with @Mock.\n"
        "9. COMPILATION: The generated test MUST compile without errors. Check for:\n"
        "   - Missing semicolons\n"
        "   - Incorrect method calls\n"
        "   - Missing imports\n"
        "   - Type conversion errors (double to int, etc.)\n"
        "   - Syntax errors\n"
        "   - Missing class references\n"
        "10. PACKAGE: Use the same package as the source class.\n"
        "11. Do not make any assumptions about code. Verify if the fucntion you are calling even exists or not.\n"
        "12. DATABASE MOCKING: For Spring Boot Application tests, use @MockBean to mock database connections and prevent real DB calls.\n"
        "13. NO REAL DATABASE: Never let tests connect to real databases - always mock database dependencies.\n"
        "14. JtSpringProjectApplication TESTS: DO NOT call SpringApplication.run() directly - mock all dependencies instead.\n"
        "15. USE @ExtendWith(MockitoExtension.class) for unit tests, NOT @SpringBootTest for database-dependent tests.\n\n"
        "CRITICAL OUTPUT FORMAT:\n"
        "- Generate ONLY the Java test code\n"
        "- Do NOT wrap code in markdown code blocks (```java ... ```)\n"
        "- Do NOT include any markdown formatting\n"
        "- Start directly with package declaration\n"
        "- End with the closing brace of the class\n\n"
        "Important final reminders for the generator:\n"
        "- Do NOT change business logic. If you think business logic is wrong, add a one-line `// NOTE:` at the top explaining the concern, then still generate tests assuming current behavior.\n"
        "- Mock repositories or external API calls — create @Mock fields and necessary stubs.\n"
        "- Do NOT use Mockito for simple POJOs with no external dependencies; instantiate directly.\n"
        "- Use `org.mockito.junit.jupiter.MockitoExtension` for @ExtendWith import; do not use `org.mockito.MockitoExtension`.\n"
        "- When using MockitoExtension, do NOT call MockitoAnnotations.openMocks.\n"
        "- Respect Java int overflow semantics; avoid impossible assertions like `Integer.MAX_VALUE + 1`.\n"
        "- If accessing private methods is required, use reflection and comment that reflection is used.\n"
        "- Before generating tests, include a brief comment block at the top with:\n"
        "  - A 1–2 line summary of code flow\n"
        "  - The branches/scenarios you will cover\n"
        "- Ensure the produced Java file compiles (imports, package, class name, annotations).\n"
        "- Output ONLY the Java test file content with no Markdown fences or backticks.\n"
        "- Use the ENHANCED CONTEXT above to understand the exact class structure, constructors, and dependencies.\n"
        "- DOUBLE-CHECK: Verify all method calls, constructor usage, and imports match the ENHANCED CONTEXT exactly.\n"
        "\n"
        "🚨 CRITICAL COMPILATION VALIDATION:\n"
        "Before returning the code, verify it will compile by checking for:\n"
        "- Missing semicolons\n"
        "- Incorrect method calls\n"
        "- Missing imports (CategoryRepository, CategoryService, etc.)\n"
        "- Type conversion errors (double to int, etc.)\n"
        "- Syntax errors\n"
        "- Missing class references\n"
        "- All imports must exist in the project\n"
        "- All method calls must exist in the actual classes\n"
        "- All types must match exactly (int not double, String not Object)\n"
        "\n"
        "🔍 TYPE CHECKING VALIDATION:\n"
        "- For each setter call, verify the parameter type matches the field type\n"
        "- If field is 'private int price', use setPrice(10) NOT setPrice(10.0)\n"
        "- If field is 'private double price', use setPrice(10.0) NOT setPrice(10)\n"
        "- If field is 'private String name', use setName(\"value\") NOT setName(123)\n"
        "- If field is 'private boolean active', use setActive(true) NOT setActive(1)\n"
        "\n"
        "🚨 CRITICAL: If you cannot verify the code will compile, DO NOT generate it. Ask for clarification instead.\n"
    )


def configure_gemini(api_key: str, model_name: str, system_prompt: str):
    if genai is None:
        raise RuntimeError(
            "google-generativeai is not installed. Install with: pip install google-generativeai"
        )
    if not api_key:
        raise RuntimeError(
            "Google API key is missing. Set the environment variable GOOGLE_API_KEY to your key."
        )
    genai.configure(api_key=api_key)

    generation_config = {
        "temperature": 0.2,
        "top_p": 0.95,
        "top_k": 32,
        "max_output_tokens": 4096,
    }

    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system_prompt,
        generation_config=generation_config,
    )
    return model


def generate_tests(model, user_prompt: str) -> str:
    # Single-turn generation; callers can add streaming if desired
    resp = model.generate_content(user_prompt)
    # google-generativeai returns text via .text when using 1.5 models
    if hasattr(resp, "text") and resp.text:
        return resp.text
    # Fallback: try to extract from candidates
    try:
        return "".join([c.text for c in resp.candidates if getattr(c, "text", None)])
    except Exception:
        pass
    raise RuntimeError("Model returned no text content.")


def strip_markdown_code_fences(text: str) -> str:
    """
    Remove leading/trailing Markdown code fences (``` or ```java) if present.
    Keeps inner content intact. No other transformations.
    """
    stripped = text.strip()
    # Leading fence
    if stripped.startswith("```"):
        # Drop the first fence line
        parts = stripped.split("\n", 1)
        stripped = parts[1] if len(parts) == 2 else ""
    # Trailing fence
    if stripped.endswith("```"):
        stripped = stripped[: -3]
        # Trim one trailing newline that usually precedes the fence
        stripped = stripped.rstrip()
    return stripped

def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate JUnit5 + Mockito tests using Gemini and PROMPT_GUIDE.md as system context",
    )
    parser.add_argument(
        "--guide",
        default="PROMPT_GUIDE.md",
        help="Path to PROMPT_GUIDE.md containing the system prompt (default: PROMPT_GUIDE.md)",
    )
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument(
        "--java",
        help="Path to a Java source file to read as input. If omitted, reads from stdin.",
    )
    parser.add_argument(
        "--out",
        help="Optional output path. If omitted, prints to stdout.",
    )
    parser.add_argument(
        "--model",
        default="gemini-1.5-pro",
        help="Gemini model to use (default: gemini-1.5-pro)",
    )
    parser.add_argument(
        "--api-key",
        dest="api_key",
        default=os.environ.get("GOOGLE_API_KEY", ""),
        help="Google API key. Defaults to $GOOGLE_API_KEY env var.",
    )
    parser.add_argument(
        "--print-system",
        action="store_true",
        help="Print the extracted system prompt and exit (for debugging).",
    )
    return parser.parse_args(argv)


def load_java_input(path: Optional[str]) -> str:
    if path:
        text = read_text_file(path)
    else:
        if sys.stdin.isatty():
            raise ValueError(
                "No --java file provided and no stdin detected. Pipe Java code or use --java <file>."
            )
        text = sys.stdin.read()
    text = text.strip()
    if not text:
        raise ValueError("Empty Java input.")
    return text


def write_output(text: str, out_path: Optional[str]) -> None:
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    try:
        guide_text = read_text_file(args.guide)
        system_prompt = extract_system_prompt(guide_text)
    except Exception as e:
        sys.stderr.write(f"Error reading/parsing guide: {e}\n")
        return 2

    if args.print_system:
        # For quick inspection/debugging
        sys.stdout.write(system_prompt + "\n")
        return 0

    try:
        java_code = load_java_input(args.java)
    except Exception as e:
        sys.stderr.write(f"Error reading Java input: {e}\n")
        return 2

    # Generate enhanced context if java file is provided
    context_file = None
    if args.java and os.path.exists(args.java):
        try:
            from enhanced_context_generator import JavaContextAnalyzer
            analyzer = JavaContextAnalyzer("JtProject/src/main/java")
            context_file = args.java.replace('.java', '_context.txt')
            context = analyzer.generate_comprehensive_context(Path(args.java))
            with open(context_file, 'w', encoding='utf-8') as f:
                f.write(context)
        except Exception as e:
            print(f"Warning: Could not generate enhanced context: {e}")

    user_prompt = build_user_prompt(java_code, context_file)

    try:
        model = configure_gemini(args.api_key, args.model, system_prompt)
        output = generate_tests(model, user_prompt)
        output = strip_markdown_code_fences(output)
    except Exception as e:
        sys.stderr.write(f"Error generating tests: {e}\n")
        return 3

    try:
        write_output(output, args.out)
    except Exception as e:
        sys.stderr.write(f"Error writing output: {e}\n")
        return 2

    return 0


def generate_test_with_prompt(java_file: Path, test_file: Path, enhanced_prompt: str) -> bool:
    """Generate test using an enhanced prompt for error-driven iteration"""
    try:
        # Read the Java source
        with open(java_file, 'r') as f:
            java_code = f.read()
        
        # Generate context
        from enhanced_context_generator import JavaContextAnalyzer
        analyzer = JavaContextAnalyzer(java_file)
        context = analyzer.generate_comprehensive_context(java_file)
        
        # Use the enhanced prompt instead of the regular one
        user_prompt = enhanced_prompt
        
        # Generate the test
        # Initialize the model
        if not genai:
            raise RuntimeError("google-generativeai not installed. Run: pip install google-generativeai")
        
        genai.configure(api_key=os.environ.get("GOOGLE_API_KEY", ""))
        model = genai.GenerativeModel("gemini-1.5-pro")
        
        # Generate the test content
        test_content = generate_tests(model, user_prompt)
        
        # Add delay to avoid rate limits
        import time
        time.sleep(2)  # Wait 2 seconds between API calls
        
        # Write the test file
        test_file.parent.mkdir(parents=True, exist_ok=True)
        with open(test_file, 'w') as f:
            f.write(test_content)
        
        return True
    except Exception as e:
        print(f"Error generating test with enhanced prompt: {e}")
        return False


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:])) 