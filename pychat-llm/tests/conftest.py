from pychat_llm.llm import LLMProvider
from pychat_llm.repository import HistoryInMemoryRepository, HistoryFileRepository, HistoryRepository
import pytest

from pychat_llm.app import ChatApp
from pychat_llm.history import HistoryService


class MockLLMProvider(LLMProvider):
    def __init__(self, response: str = "Mock response"):
        self._response = response

    async def get_response(self, prompt: str, history: list) -> str:
        return self._response

    def get_welcome_message(self) -> str:
        return "Mock welcome"


@pytest.fixture
def mock_llm():
    return MockLLMProvider()


@pytest.fixture(params=["in_memory", "file"])
def history_repo(request, tmp_path) -> HistoryRepository:
    if request.param == "in_memory":
        return HistoryInMemoryRepository()
    return HistoryFileRepository(str(tmp_path / "history"))


@pytest.fixture
def history_service(history_repo):
    return HistoryService(history_repo=history_repo)


@pytest.fixture
def app_with_service(history_service, mock_llm):
    return ChatApp(history_service=history_service, llm_provider=mock_llm)
