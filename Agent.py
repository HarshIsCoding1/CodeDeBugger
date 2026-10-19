"""
Simple bug-fixing coding agent (no LangGraph, no frameworks).

Setup:
    pip install openai
    export XAI_API_KEY="your-key"        # Windows: set XAI_API_KEY=your-key
    (optional) export GROK_MODEL="grok-4"

Run:
    python agent.py              # works on the current folder
    python agent.py path/to/dir  # works on another folder

Flow:
    1. You describe the bug in plain English.
    2. Grok uses tools (search_files, search_in_file, read_file, replace_line,
       compile_and_run) to find and fix the bug.
    3. When Grok says it is fixed, we compile + run the program and ask YOU
       whether the output is now correct.
    4. If not fixed, we restore the original files and retry (max 3 attempts).
"""

import json
import os
import subprocess
import sys
import tempfile
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------
MAX_ATTEMPTS = 3          # max retries
MAX_STEPS_PER_ATTEMPT = 15  # max LLM <-> tool round trips inside one attempt
MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
SOURCE_EXTENSIONS = (".cpp", ".cc", ".c", ".h", ".hpp")

WORKSPACE = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.getcwd())


api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("GROQ_API_KEY not found in .env file")

client = OpenAI(
    api_key=api_key,
    base_url="https://api.groq.com/openai/v1",
)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def safe_path(path):
    """Resolve a path and make sure it stays inside the workspace."""
    full = path if os.path.isabs(path) else os.path.join(WORKSPACE, path)
    full = os.path.abspath(full)
    if not full.startswith(WORKSPACE):
        raise ValueError(f"Path '{path}' is outside the workspace.")
    if not os.path.isfile(full):
        raise ValueError(f"File '{path}' does not exist.")
    return full


def rel(path):
    return os.path.relpath(path, WORKSPACE)


def all_source_files():
    found = []
    for root, dirs, files in os.walk(WORKSPACE):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in files:
            if name.endswith(SOURCE_EXTENSIONS):
                found.append(os.path.join(root, name))
    return sorted(found)


def read_lines(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read().split("\n")


def write_lines(path, lines):
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ----------------------------------------------------------------------------
# Tools (the functions the LLM can call)
# ----------------------------------------------------------------------------
def search_files(keywords):
    """Return paths of source files that contain any of the keywords."""
    keywords = [k.lower() for k in keywords]
    results = []
    for path in all_source_files():
        text = "\n".join(read_lines(path)).lower()
        hits = sum(text.count(k) for k in keywords)
        if hits:
            results.append((hits, rel(path)))
    if not results:
        return "No files matched. Try different keywords, or use more general ones."
    results.sort(reverse=True)
    return "\n".join(f"{p}  ({h} keyword hits)" for h, p in results)


def search_in_file(path, keywords):
    """Return line numbers (and text) in a file that contain any keyword."""
    full = safe_path(path)
    keywords = [k.lower() for k in keywords]
    out = []
    for i, line in enumerate(read_lines(full), start=1):
        if any(k in line.lower() for k in keywords):
            out.append(f"{i}: {line}")
    return "\n".join(out) if out else "No lines matched those keywords."


def read_file(path, start_line=1, end_line=None):
    """Return the given line range with line numbers."""
    full = safe_path(path)
    lines = read_lines(full)
    end_line = end_line or len(lines)
    start_line = max(1, start_line)
    end_line = min(len(lines), end_line)
    return "\n".join(f"{i}: {lines[i - 1]}" for i in range(start_line, end_line + 1))


def replace_line(path, line_number, new_content):
    """Replace exactly one line (1-indexed) with new_content."""
    full = safe_path(path)
    lines = read_lines(full)
    if not (1 <= line_number <= len(lines)):
        return f"ERROR: line_number {line_number} out of range (file has {len(lines)} lines)."
    old = lines[line_number - 1]
    lines[line_number - 1] = new_content
    write_lines(full, lines)
    return f"Replaced line {line_number} in {path}\n  OLD: {old}\n  NEW: {new_content}"


def compile_and_run(path):
    """Compile a C++ file with g++ and run it. Returns compiler errors or program output."""
    full = safe_path(path)
    exe = os.path.join(tempfile.gettempdir(), "agent_program")
    compile_proc = subprocess.run(
        ["g++", "-std=c++17", "-Wall", full, "-o", exe],
        capture_output=True, text=True,
    )
    if compile_proc.returncode != 0:
        return f"COMPILE ERROR:\n{compile_proc.stderr[:3000]}"
    try:
        run_proc = subprocess.run(
            [exe], capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL
        )
    except subprocess.TimeoutExpired:
        return "RUNTIME ERROR: program timed out after 10 seconds."
    out = f"Exit code: {run_proc.returncode}\n--- stdout ---\n{run_proc.stdout[:3000]}"
    if run_proc.stderr:
        out += f"\n--- stderr ---\n{run_proc.stderr[:1000]}"
    return out


TOOL_FUNCTIONS = {
    "search_files": search_files,
    "search_in_file": search_in_file,
    "read_file": read_file,
    "replace_line": replace_line,
    "compile_and_run": compile_and_run,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search all source files in the project and list the PATHS of files related to the bug, based on keywords.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keywords": {"type": "array", "items": {"type": "string"},
                                 "description": "Keywords related to the bug (function names, variables, concepts)."}
                },
                "required": ["keywords"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_in_file",
            "description": "Search inside ONE file and return the LINE NUMBERS (with the line text) matching the keywords.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["path", "keywords"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a range of lines from a file (with line numbers). Use this to inspect code around a suspicious line before editing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "replace_line",
            "description": "Replace ONE line (by 1-indexed line number) with new content. Include the correct indentation in new_content. Replace single lines only; do not include newline characters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "line_number": {"type": "integer"},
                    "new_content": {"type": "string"},
                },
                "required": ["path", "line_number", "new_content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compile_and_run",
            "description": "Compile the given C++ file and run it. Use this after editing to check that it compiles and the output is correct.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "report_fixed",
            "description": "Call this ONLY when you have made your fix and verified it by running the program. Ends the attempt.",
            "parameters": {
                "type": "object",
                "properties": {"summary": {"type": "string", "description": "What was wrong and what you changed."}},
                "required": ["summary"],
            },
        },
    },
]

SYSTEM_PROMPT = """You are a coding agent that fixes simple bugs in C++ projects.
The user describes a bug in plain English. Work like this:
1. Use search_files to find which files relate to the bug.
2. Use search_in_file to find relevant line numbers, and read_file to inspect the code.
3. Fix it with replace_line (one line at a time; line numbers do not shift because you replace single lines).
4. Run compile_and_run to verify your fix compiles and the output is correct.
5. Call report_fixed with a short summary.
Make the smallest change needed. Do not change unrelated code."""


# ----------------------------------------------------------------------------
# Agent loop
# ----------------------------------------------------------------------------
def short(text, limit=300):
    text = str(text)
    return text if len(text) <= limit else text[:limit] + " ...[truncated]"


def run_attempt(attempt, bug, previous_failures):
    """One attempt. Returns (finished, summary)."""
    user_msg = f"Bug description: {bug}\nProject folder: {WORKSPACE}"
    if previous_failures:
        user_msg += "\n\nPrevious attempts FAILED. Files were restored to their original state.\n"
        user_msg += "\n".join(f"- Attempt {i + 1}: {f}" for i, f in enumerate(previous_failures))
        user_msg += "\nTry a different approach."

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    for step in range(1, MAX_STEPS_PER_ATTEMPT + 1):
        print(f"\n  --- Attempt {attempt}/{MAX_ATTEMPTS} | Step {step} ---")
        response = client.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOL_SCHEMAS, tool_choice="auto"
        )
        msg = response.choices[0].message
        messages.append(msg)

        if msg.content:
            print(f"  [LLM says] {short(msg.content)}")

        if not msg.tool_calls:
            # Model stopped without calling report_fixed -> nudge it
            print("  [No tool called] asking the LLM to continue or call report_fixed...")
            messages.append({"role": "user",
                             "content": "Continue using tools, or call report_fixed if you are done."})
            continue

        for call in msg.tool_calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            print(f"  [TOOL CALLED] {name}({json.dumps(args)})")

            if name == "report_fixed":
                summary = args.get("summary", "")
                print(f"  [LLM reports fixed] {summary}")
                return True, summary

            try:
                result = TOOL_FUNCTIONS[name](**args)
            except Exception as e:  # bad args / bad path etc. -> tell the LLM
                result = f"ERROR: {e}"
            print(f"  [TOOL RESULT] {short(result)}")
            messages.append({"role": "tool", "tool_call_id": call.id, "content": str(result)})

    return False, f"Ran out of steps ({MAX_STEPS_PER_ATTEMPT}) without finishing."


def main():
    if not os.environ.get("XAI_API_KEY"):
        print("Please set the XAI_API_KEY environment variable first.")
        sys.exit(1)

    sources = all_source_files()
    if not sources:
        print(f"No C/C++ source files found in {WORKSPACE}")
        sys.exit(1)

    print(f"Workspace: {WORKSPACE}")
    print("Source files: " + ", ".join(rel(p) for p in sources))
    bug = input("\nDescribe the bug in plain English: ").strip()
    if not bug:
        print("No bug given. Exiting.")
        return

    # Snapshot originals so every retry starts from a clean state
    snapshot = {p: read_lines(p) for p in sources}
    failures = []

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"\n===== ATTEMPT {attempt} of {MAX_ATTEMPTS} =====")
        finished, summary = run_attempt(attempt, bug, failures)

        if finished:
            # Verify by compiling + running, then ask the human
            print("\n  [HARNESS] Compiling and running the program to verify...")
            main_file = next((p for p in sources if os.path.basename(p) == "main.cpp"), sources[0])
            result = compile_and_run(main_file)
            print(result)

            if result.startswith("COMPILE ERROR") or result.startswith("RUNTIME ERROR"):
                failures.append(f"Fix did not compile/run: {short(result, 400)}")
            else:
                answer = input("\nIs the bug fixed? (y/n): ").strip().lower()
                if answer == "y":
                    print("\n✅ Bug fixed. Changes are saved in your file(s).")
                    return
                reason = input("What is still wrong? (press Enter to skip): ").strip()
                failures.append(f"User said it was NOT fixed. {reason}  (LLM had tried: {summary})")
        else:
            failures.append(summary)

        # Restore originals before retrying (or before giving up)
        for path, lines in snapshot.items():
            write_lines(path, lines)
        print("  [HARNESS] Restored original files.")

    print(f"\n❌ Sorry, I could not solve this bug within {MAX_ATTEMPTS} attempts. Original files were restored.")


if __name__ == "__main__":
    main()