# nanocode

Minimal Claude Code alternative. Single Python file, zero dependencies, ~250 lines.

Built using Claude Code, then used to build itself.

![screenshot](screenshot.png)

## Features

- Full agentic loop with tool use
- Tools: `read`, `write`, `edit`, `glob`, `grep`, `bash`
- Conversation history
- Colored terminal output

## Usage

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=your-key
MODEL=claude-sonnet-4-6
```

Then run:

```bash
python nanocode.py
```

### OpenRouter

Use [OpenRouter](https://openrouter.ai) to access any model:

```
OPENROUTER_API_KEY=your-key
```

To use a different model:

```
OPENROUTER_API_KEY=your-key
MODEL=openai/gpt-5.2
```

Environment variables also work and take precedence over `.env`.

## Commands

- `/c` - Clear conversation
- `/q` or `exit` - Quit

## Tools

| Tool    | Description                               |
| ------- | ----------------------------------------- |
| `read`  | Read file with line numbers, offset/limit |
| `write` | Write content to file                     |
| `edit`  | Replace string in file (must be unique)   |
| `glob`  | Find files by pattern, sorted by mtime    |
| `grep`  | Search files for regex                    |
| `bash`  | Run shell command                         |

## Example

```
────────────────────────────────────────
❯ what files are here?
────────────────────────────────────────

⏺ Glob(**/*.py)
  ⎿  nanocode.py

⏺ There's one Python file: nanocode.py
```

## License

MIT
