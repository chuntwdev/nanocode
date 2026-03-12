#!/usr/bin/env python3
"""nanocode - minimal claude code alternative"""

import glob as globlib, importlib, json, os, re, subprocess, sys, urllib.request


def load_env(path=".env"):
    try:
        for line in open(path):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))
    except FileNotFoundError:
        pass


CONFIG_PATH = os.path.expanduser("~/.config/nanocode/.env")

load_env(CONFIG_PATH)
load_env()

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY")
API_URL = "https://openrouter.ai/api/v1/messages" if OPENROUTER_KEY else "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("MODEL", "anthropic/claude-opus-4.5" if OPENROUTER_KEY else "claude-opus-4-5")

# ANSI colors
RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
BLUE, CYAN, GREEN, YELLOW, RED = (
    "\033[34m",
    "\033[36m",
    "\033[32m",
    "\033[33m",
    "\033[31m",
)

try:
    _rich_console_mod = importlib.import_module("rich.console")
    _rich_markdown_mod = importlib.import_module("rich.markdown")
    RICH_CONSOLE = _rich_console_mod.Console(record=True, force_terminal=True)
    RICH_MARKDOWN = _rich_markdown_mod.Markdown
except Exception:
    RICH_CONSOLE = None
    RICH_MARKDOWN = None


# --- Setup / onboarding ---


def fetch_models(provider, api_key):
    if provider == "anthropic":
        url = "https://api.anthropic.com/v1/models?limit=1000"
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
    else:
        url = "https://openrouter.ai/api/v1/models"
        headers = {"Authorization": f"Bearer {api_key}"}
    req = urllib.request.Request(url, headers=headers)
    data = json.loads(urllib.request.urlopen(req).read())
    return sorted(m["id"] for m in data.get("data", []))


def pick_model(models):
    while True:
        query = input(f"\n  {BOLD}Filter{RESET} (or Enter to show all): ").strip().lower()
        filtered = [m for m in models if query in m.lower()] if query else models
        if not filtered:
            print(f"  {DIM}No matches, try again.{RESET}")
            continue
        for i, m in enumerate(filtered[:20], 1):
            print(f"    {BOLD}{i:>2}){RESET} {m}")
        if len(filtered) > 20:
            print(f"    {DIM}... +{len(filtered) - 20} more, narrow your filter{RESET}")
            continue
        choice = input(f"\n  {BOLD}Select{RESET} [1]: ").strip()
        try:
            idx = int(choice) - 1 if choice else 0
        except ValueError:
            continue
        if 0 <= idx < len(filtered):
            return filtered[idx]


def setup():
    print(f"\n  {BOLD}nanocode setup{RESET}\n")
    print(f"  {BOLD}1){RESET} Anthropic")
    print(f"  {BOLD}2){RESET} OpenRouter")
    choice = input(f"\n  Provider [1]: ").strip()
    provider = "openrouter" if choice == "2" else "anthropic"

    key_name = "OPENROUTER_API_KEY" if provider == "openrouter" else "ANTHROPIC_API_KEY"
    api_key = input(f"  {key_name}: ").strip()
    if not api_key:
        print(f"\n  {RED}No API key provided.{RESET}")
        return None

    print(f"\n  {DIM}Fetching models...{RESET}")
    try:
        models = fetch_models(provider, api_key)
    except Exception as e:
        print(f"\n  {RED}Failed to fetch models: {e}{RESET}")
        return None

    if not models:
        print(f"\n  {RED}No models found.{RESET}")
        return None

    print(f"  {GREEN}Found {len(models)} models{RESET}")
    model = pick_model(models)

    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        f.write(f"{key_name}={api_key}\nMODEL={model}\n")

    print(f"\n  {GREEN}Saved to {CONFIG_PATH}{RESET}\n")
    return key_name, api_key, model


# --- Tool implementations ---


def read(args):
    lines = open(args["path"]).readlines()
    offset = args.get("offset", 0)
    limit = args.get("limit", len(lines))
    selected = lines[offset : offset + limit]
    return "".join(f"{offset + idx + 1:4}| {line}" for idx, line in enumerate(selected))


def write(args):
    with open(args["path"], "w") as f:
        f.write(args["content"])
    return "ok"


def edit(args):
    text = open(args["path"]).read()
    old, new = args["old"], args["new"]
    if old not in text:
        return "error: old_string not found"
    count = text.count(old)
    if not args.get("all") and count > 1:
        return f"error: old_string appears {count} times, must be unique (use all=true)"
    replacement = (
        text.replace(old, new) if args.get("all") else text.replace(old, new, 1)
    )
    with open(args["path"], "w") as f:
        f.write(replacement)
    return "ok"


def glob(args):
    pattern = (args.get("path", ".") + "/" + args["pat"]).replace("//", "/")
    files = globlib.glob(pattern, recursive=True)
    files = sorted(
        files,
        key=lambda f: os.path.getmtime(f) if os.path.isfile(f) else 0,
        reverse=True,
    )
    return "\n".join(files) or "none"


def grep(args):
    pattern = re.compile(args["pat"])
    hits = []
    for filepath in globlib.glob(args.get("path", ".") + "/**", recursive=True):
        try:
            for line_num, line in enumerate(open(filepath), 1):
                if pattern.search(line):
                    hits.append(f"{filepath}:{line_num}:{line.rstrip()}")
        except Exception:
            pass
    return "\n".join(hits[:50]) or "none"


def bash(args):
    proc = subprocess.Popen(
        args["cmd"], shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True
    )
    output_lines = []
    try:
        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None:
                break
            if line:
                print(f"  {DIM}│ {line.rstrip()}{RESET}", flush=True)
                output_lines.append(line)
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        output_lines.append("\n(timed out after 30s)")
    return "".join(output_lines).strip() or "(empty)"


# --- Tool definitions: (description, schema, function) ---

TOOLS = {
    "read": (
        "Read file with line numbers (file path, not directory)",
        {"path": "string", "offset": "number?", "limit": "number?"},
        read,
    ),
    "write": (
        "Write content to file",
        {"path": "string", "content": "string"},
        write,
    ),
    "edit": (
        "Replace old with new in file (old must be unique unless all=true)",
        {"path": "string", "old": "string", "new": "string", "all": "boolean?"},
        edit,
    ),
    "glob": (
        "Find files by pattern, sorted by mtime",
        {"pat": "string", "path": "string?"},
        glob,
    ),
    "grep": (
        "Search files for regex pattern",
        {"pat": "string", "path": "string?"},
        grep,
    ),
    "bash": (
        "Run shell command",
        {"cmd": "string"},
        bash,
    ),
}


def run_tool(name, args):
    try:
        return TOOLS[name][2](args)
    except Exception as err:
        return f"error: {err}"


def make_schema():
    result = []
    for name, (description, params, _fn) in TOOLS.items():
        properties = {}
        required = []
        for param_name, param_type in params.items():
            is_optional = param_type.endswith("?")
            base_type = param_type.rstrip("?")
            properties[param_name] = {
                "type": "integer" if base_type == "number" else base_type
            }
            if not is_optional:
                required.append(param_name)
        result.append(
            {
                "name": name,
                "description": description,
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            }
        )
    return result


def call_api(messages, system_prompt):
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(
            {
                "model": MODEL,
                "max_tokens": 8192,
                "system": system_prompt,
                "messages": messages,
                "tools": make_schema(),
            }
        ).encode(),
        headers={
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            **({"Authorization": f"Bearer {OPENROUTER_KEY}"} if OPENROUTER_KEY else {"x-api-key": os.environ.get("ANTHROPIC_API_KEY", "")}),
        },
    )
    response = urllib.request.urlopen(request)
    return json.loads(response.read())


def separator():
    return f"{DIM}{'─' * min(os.get_terminal_size().columns, 80)}{RESET}"


def render_markdown(text):
    if not RICH_CONSOLE or not RICH_MARKDOWN:
        return re.sub(r"\*\*(.+?)\*\*", f"{BOLD}\\1{RESET}", text)
    with RICH_CONSOLE.capture() as capture:
        RICH_CONSOLE.print(RICH_MARKDOWN(text))
    return capture.get().rstrip("\n")


def main():
    global OPENROUTER_KEY, API_URL, MODEL

    needs_setup = "--setup" in sys.argv or (
        not os.path.exists(CONFIG_PATH)
        and not os.environ.get("ANTHROPIC_API_KEY")
        and not os.environ.get("OPENROUTER_API_KEY")
    )

    if needs_setup:
        result = setup()
        if not result:
            return
        key_name, api_key, model = result
        os.environ[key_name] = api_key
        os.environ["MODEL"] = model
        OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY")
        API_URL = "https://openrouter.ai/api/v1/messages" if OPENROUTER_KEY else "https://api.anthropic.com/v1/messages"
        MODEL = model

    print(f"{BOLD}nanocode{RESET} | {DIM}{MODEL} ({'OpenRouter' if OPENROUTER_KEY else 'Anthropic'}) | {os.getcwd()}{RESET}\n")
    messages = []
    system_prompt = f"Concise coding assistant. cwd: {os.getcwd()}"

    while True:
        try:
            print(separator())
            user_input = input(f"{BOLD}{BLUE}❯{RESET} ").strip()
            print(separator())
            if not user_input:
                continue
            if user_input in ("/q", "exit"):
                break
            if user_input == "/c":
                messages = []
                print(f"{GREEN}⏺ Cleared conversation{RESET}")
                continue

            messages.append({"role": "user", "content": user_input})

            # agentic loop: keep calling API until no more tool calls
            while True:
                response = call_api(messages, system_prompt)
                content_blocks = response.get("content", [])
                tool_results = []

                for block in content_blocks:
                    if block["type"] == "text":
                        print(f"\n{CYAN}⏺{RESET} {render_markdown(block['text'])}")

                    if block["type"] == "tool_use":
                        tool_name = block["name"]
                        tool_args = block["input"]
                        arg_preview = str(list(tool_args.values())[0])[:50]
                        print(
                            f"\n{GREEN}⏺ {tool_name.capitalize()}{RESET}({DIM}{arg_preview}{RESET})"
                        )

                        result = run_tool(tool_name, tool_args)
                        result_lines = result.split("\n")
                        preview = result_lines[0][:60]
                        if len(result_lines) > 1:
                            preview += f" ... +{len(result_lines) - 1} lines"
                        elif len(result_lines[0]) > 60:
                            preview += "..."
                        print(f"  {DIM}⎿  {preview}{RESET}")

                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block["id"],
                                "content": result,
                            }
                        )

                messages.append({"role": "assistant", "content": content_blocks})

                if not tool_results:
                    break
                messages.append({"role": "user", "content": tool_results})

            print()

        except (KeyboardInterrupt, EOFError):
            break
        except Exception as err:
            print(f"{RED}⏺ Error: {err}{RESET}")


if __name__ == "__main__":
    main()
