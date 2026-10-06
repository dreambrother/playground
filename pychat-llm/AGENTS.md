# pychat-llm

## What this is
Textual TUI chat app (Python). Supports both a mock LLM provider and OpenAI-compatible APIs via optional `config.toml`.

## Setup & run
```
poetry install
poetry run pychat-llm   # or: python -m pychat_llm.cli
```

### CLI options
- `-s`, `--storage` — storage backend: `file` (default) or `memory`
- `--word-limit` — max words in chat context, 0=unlimited (default: 10000). Old messages in memory are trimmed; full history stays on disk.

Example:
```
poetry run pychat-llm --storage memory
python -m pychat_llm.cli -s memory
```

### OpenAI-compatible provider
Create a `config.toml` in the working directory to switch from `DummyLLMProvider` to `OpenAIProvider`:

```toml
token = "sk-..."
url = "https://api.openai.com/v1"
# optional:
# model = "gpt-4o-mini"
```

Aliases `api_key` / `base_url` are also supported. If the file is missing or incomplete, the app falls back to `DummyLLMProvider`.

Config format is TOML — parsed with the built-in `tomllib` (no extra dependencies).

## Project structure
- `src/pychat_llm/cli.py` — composition root: CLI args, dependency wiring, `main()`
- `src/pychat_llm/app.py` — UI widgets (`ChatApp`, `ChatListScreen`, `ChatInput`, `MessageBubble`, `MessageContainer`)
- `src/pychat_llm/history.py` — `HistoryService` coordinating LLM and repository; trims in-memory chat to `word_limit` words, uses `load_recent` for efficient loading
- `src/pychat_llm/llm.py` — `LLMProvider` abstract base class, `DummyLLMProvider`, and `OpenAIProvider` implementations
- `src/pychat_llm/repository.py` — data access layer (abstract + file/in-memory implementations). `load_recent` reads recent messages backwards from file, counting words until limit.
- `tests/` — pytest integration tests with mocked LLM and real file I/O
- `ConfigScreen` in `app.py` — modal screen for editing `config.toml` (token, url, model). Token is masked (`password=True`). Opened via `Ctrl+Shift+C`.

## Code organization
- **Top-to-bottom reading order** — high-level entry points (e.g., `main()`) come first; helper functions they call are defined below them
- **Classes in modules** — main class (entrypoint) should be defined first, before classes it uses
- CSS should be defined in the class it belongs to, not in parent containers

## Anti-patterns to avoid
- **High-level modules must not depend on low-level modules** — use abstractions (`Protocol`/`ABC`)
- Dependencies should be injected via constructor, not imported directly in modules that use them
- **Each class has one reason to change** — UI classes handle UI, service classes handle business logic

## Key details
- Update `AGENTS.md` whenever implementation changes
- Package manager: **Poetry** (v2+ build backend)
- Python: **>=3.14**
- CLI entry: `pychat-llm` → `pychat_llm.cli:main`

## Testing

Tests use **pytest** with **pytest-asyncio** for async Textual app testing.

### Running tests
```
poetry run python -m pytest tests/ -v
```

### Testing approach
Integration tests with real files from temporary directories and mocked LLM providers.

**Key patterns:**
- `app.run_test()` — runs Textual app in test mode, returns Pilot for interaction
- `pilot.click("#widget-id")` — focus widget before typing
- `pilot.press("enter")` — simulate key presses
- `pilot.pause()` — allow async operations to complete
- `history_module.HISTORY_DIR = tmp_path` — redirect file storage to temp directory

**Fixtures (conftest.py):**
- `mock_llm` — test `MockLLMProvider` (configurable response, defined in `conftest.py`)
- `mock_persistence` — `MagicMock` for service-layer testing
- `app_with_service` — `ChatApp` with mock service (UI + service integration)
- `app_with_real_persistence` — `ChatApp` with real `HistoryFileRepository` using temp directory

**Test structure:**
```
tests/
├── conftest.py     # fixtures
├── test_app.py     # integration tests (UI, one test per case)
├── test_llm.py     # unit tests for LLM providers
└── test_cli.py     # unit tests for CLI configuration logic
```

### Writing new tests
1. Use `app_with_service` for tests needing controlled LLM responses
2. Use inline temp path setup for tests needing real file I/O (see existing examples)
3. Always call `await pilot.pause()` after async operations
4. For message input: click textarea first, set `.text`, then press Enter
5. Mock `OpenAI` client when testing `OpenAIProvider` to avoid network calls
6. Use `monkeypatch.chdir(tmp_path)` when testing `config.toml` discovery in `cli.py`
7. For ConfigScreen tests: create `ChatApp` directly with `HistoryInMemoryRepository`, use `monkeypatch.chdir(tmp_path)` to control config file location, use `pilot.press("ctrl+shift+c")` to open, set `Input.value` directly on screen widgets
