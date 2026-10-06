import argparse
import tomllib
from pathlib import Path

from pychat_llm.app import ChatApp
from pychat_llm.history import HistoryService
from pychat_llm.llm import DummyLLMProvider, OpenAIProvider
from pychat_llm.repository import HistoryFileRepository, HistoryInMemoryRepository


def main():
    parser = argparse.ArgumentParser(description="PyChat LLM")
    parser.add_argument(
        "-s", "--storage",
        choices=["file", "memory"],
        default="file",
        help="Storage backend (default: file)",
    )
    parser.add_argument(
        "--word-limit",
        type=int,
        default=10000,
        help="Max words in chat context, 0=unlimited (default: 10000)",
    )
    args = parser.parse_args()

    app = ChatApp(
        HistoryService(_create_repository(args.storage), word_limit=args.word_limit),
        _create_llm_provider(),
    )
    app.run()


def _create_repository(storage: str):
    if storage == "memory":
        return HistoryInMemoryRepository()
    return HistoryFileRepository("history")


def _create_llm_provider():
    config_provider = _load_config()
    if config_provider:
        return config_provider
    return DummyLLMProvider()


def _load_config(path: Path = Path("config.toml")) -> OpenAIProvider | None:
    if not path.exists():
        return None
    try:
        with open(path, "rb") as f:
            config = tomllib.load(f)
    except Exception:
        return None
    if not config:
        return None
    token = config.get("token") or config.get("api_key")
    base_url = config.get("url") or config.get("base_url")
    if not token or not base_url:
        return None
    model = config.get("model", "gpt-4o-mini")
    return OpenAIProvider(api_key=token, base_url=base_url, model=model)


if __name__ == "__main__":
    main()
