#!/usr/bin/env python3

import argparse
import os
import re
import sys
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


def build_user_prompt(java_code: str) -> str:
    # Mirrors the User Prompt Template in PROMPT_GUIDE.md
    return (
        "Generate a JUnit5 + Mockito test class for the following Java code. "
        "Follow the system instructions provided.\n\n"
        "Java code:\n"
        f"{java_code}\n\n"
        "END.\n\n"
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
        "  - Any assumptions made\n"
        "- Ensure the produced Java file compiles (imports, package, class name, annotations).\n"
        "- Output ONLY the Java test file content with no Markdown fences or backticks.\n"
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

    user_prompt = build_user_prompt(java_code)

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


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:])) 