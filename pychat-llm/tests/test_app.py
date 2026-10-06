import pytest

from datetime import datetime
from pychat_llm.app import ChatApp, ChatInput, ConfigScreen, MessageBubble
from textual.widgets import Input
from pychat_llm.domain import ChatMessage, HistoryItem
from pychat_llm.history import HistoryService
from pychat_llm.llm import DummyLLMProvider, LLMProvider, OpenAIProvider
from pychat_llm.repository import HistoryInMemoryRepository


class _MockLLM(LLMProvider):
    async def get_response(self, prompt: str, history: list) -> str:
        return "mock"

    def get_welcome_message(self) -> str:
        return "mock welcome"


class TestWelcomeMessage:
    @pytest.mark.asyncio
    async def test_welcome_message_displayed_on_app_open(self, app_with_service):
        app = app_with_service
        async with app.run_test() as pilot:
            await pilot.pause()
            container = app.query_one("#messages")
            bubbles = list(container.query(MessageBubble))
            assert len(bubbles) >= 1
            welcome = bubbles[0]
            assert "Mock welcome" in welcome.text


class TestMessageSending:
    @pytest.mark.asyncio
    async def test_user_message_displayed_in_chat(self, app_with_service):
        app = app_with_service
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#message-input")
            textarea = app.query_one("#message-input", ChatInput)
            textarea.text = "Hello world"
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()
            container = app.query_one("#messages")
            bubbles = list(container.query(MessageBubble))
            user_messages = [b for b in bubbles if b.is_user]
            assert len(user_messages) >= 1, f"Expected user message, got {len(user_messages)} bubbles: {[b.text for b in bubbles]}"
            assert any("Hello world" in b.text for b in user_messages)

    @pytest.mark.asyncio
    async def test_llm_response_displayed_after_user_message(self, app_with_service):
        app = app_with_service
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#message-input")
            textarea = app.query_one("#message-input", ChatInput)
            textarea.text = "Test message"
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()
            container = app.query_one("#messages")
            bubbles = list(container.query(MessageBubble))
            assistant_messages = [b for b in bubbles if not b.is_user]
            assert len(assistant_messages) >= 1, f"Expected assistant message, got {len(assistant_messages)} bubbles"
            assert any("Mock response" in b.text for b in assistant_messages)


class TestHistoryPersistence:
    @pytest.mark.asyncio
    async def test_history_saved_on_app_unmount(self, mock_llm, history_repo):
        history_service = HistoryService(history_repo=history_repo)
        app = ChatApp(history_service=history_service, llm_provider=mock_llm)

        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#message-input")
            textarea = app.query_one("#message-input", ChatInput)
            textarea.text = "First message"
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()

        chats = history_repo.list_chats()
        assert len(chats) >= 1, f"Expected at least 1 saved chat, got {len(chats)}"
        title, messages = history_service.get_chat()
        assert any("First message" in msg.text for msg in messages)

    @pytest.mark.asyncio
    async def test_subsequent_messages_appended_to_same_chat(self, mock_llm, history_repo):
        history_service = HistoryService(history_repo=history_repo)
        app = ChatApp(history_service=history_service, llm_provider=mock_llm)

        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#message-input")
            textarea = app.query_one("#message-input", ChatInput)
            textarea.text = "Message one"
            await pilot.press("enter")
            await pilot.pause()
            textarea.text = "Message two"
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()

        chats = history_repo.list_chats()
        assert len(chats) == 1, f"Expected 1 saved chat, got {len(chats)}"
        title, messages = history_service.get_chat()
        assert any("Message one" in msg.text for msg in messages)
        assert any("Message two" in msg.text for msg in messages)


class TestHistoryList:
    @pytest.mark.asyncio
    async def test_history_list_displays_saved_chats(self, mock_llm, history_repo):
        now = datetime.now()
        history_item = HistoryItem(id="test_chat", title="Test Chat", created_at=now)
        chat_messages = [
            ChatMessage(id=1, text="Welcome", is_user=False, created_at=now),
            ChatMessage(id=2, text="Hello", is_user=True, created_at=now),
        ]
        history_repo.save(history_item)
        history_repo.add_to_chat(history_item.id, *chat_messages)
        history_service = HistoryService(history_repo=history_repo)
        app = ChatApp(history_service=history_service, llm_provider=mock_llm)

        async with app.run_test() as pilot:
            await pilot.pause()
            app.action_open_chat()
            await pilot.pause()
            screen = app.screen
            list_view = screen.query_one("#chat-list-view")
            items = list(list_view.query_children())
            assert len(items) >= 1


class TestChatLoading:
    @pytest.mark.asyncio
    async def test_loaded_chat_appends_to_same_file(self, mock_llm, history_repo):
        now = datetime.now()
        history_item = HistoryItem(id="existing_chat", title="Existing Chat", created_at=now)
        chat_messages = [
            ChatMessage(id=1, text="Welcome", is_user=False, created_at=now),
            ChatMessage(id=2, text="User message", is_user=True, created_at=now),
        ]
        history_repo.save(history_item)
        history_repo.add_to_chat(history_item.id, *chat_messages)
        history_service = HistoryService(history_repo=history_repo)
        app = ChatApp(history_service=history_service, llm_provider=mock_llm)

        async with app.run_test() as pilot:
            await pilot.pause()
            app._load_chat("existing_chat")
            await pilot.pause()
            await pilot.click("#message-input")
            textarea = app.query_one("#message-input", ChatInput)
            textarea.text = "New message"
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()

        chats = history_repo.list_chats()
        assert len(chats) == 1, f"Expected 1 chat, got {len(chats)}: {[c.id for c in chats]}"
        assert chats[0].id == "existing_chat"
        _, messages = history_service.load_chat("existing_chat")
        assert any("New message" in msg.text for msg in messages)


class TestConfigScreen:
    def _create_app(self):
        return ChatApp(
            history_service=HistoryService(HistoryInMemoryRepository()),
            llm_provider=_MockLLM(),
        )

    @pytest.mark.asyncio
    async def test_config_screen_opens_on_keybinding(self, app_with_service):
        app = app_with_service
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+shift+c")
            await pilot.pause()
            assert isinstance(app.screen, ConfigScreen)
            screen = app.screen
            assert screen.query_one("#config-url")
            assert screen.query_one("#config-token")
            assert screen.query_one("#config-model")
            assert screen.query_one("#config-save")
            assert screen.query_one("#config-cancel")

    @pytest.mark.asyncio
    async def test_prefills_from_existing_config(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            'token = "sk-secret"\n'
            'url = "https://api.example.com/v1"\n'
            'model = "gpt-4"\n'
        )
        monkeypatch.chdir(tmp_path)
        app = self._create_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+shift+c")
            await pilot.pause()
            screen = app.screen
            assert screen.query_one("#config-url", Input).value == "https://api.example.com/v1"
            assert screen.query_one("#config-token", Input).password is True
            assert screen.query_one("#config-token", Input).value == "sk-secret"
            assert screen.query_one("#config-model", Input).value == "gpt-4"

    @pytest.mark.asyncio
    async def test_prefills_from_alias_fields(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            'api_key = "sk-alias"\n'
            'base_url = "https://alias.example.com/v1"\n'
        )
        monkeypatch.chdir(tmp_path)
        app = self._create_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+shift+c")
            await pilot.pause()
            screen = app.screen
            assert screen.query_one("#config-url", Input).value == "https://alias.example.com/v1"
            assert screen.query_one("#config-token", Input).value == "sk-alias"
            assert screen.query_one("#config-model", Input).value == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_save_writes_config_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        app = self._create_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+shift+c")
            await pilot.pause()
            screen = app.screen
            screen.query_one("#config-url", Input).value = "https://api.test.com/v1"
            screen.query_one("#config-token", Input).value = "sk-test"
            screen.query_one("#config-model", Input).value = "gpt-3.5"
            await pilot.click("#config-save")
            await pilot.pause()
        content = (tmp_path / "config.toml").read_text()
        assert "sk-test" in content
        assert "https://api.test.com/v1" in content
        assert "gpt-3.5" in content

    @pytest.mark.asyncio
    async def test_save_switches_to_openai_provider(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        app = self._create_app()
        assert isinstance(app._llm_provider, _MockLLM)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+shift+c")
            await pilot.pause()
            screen = app.screen
            screen.query_one("#config-url", Input).value = "https://api.test.com/v1"
            screen.query_one("#config-token", Input).value = "sk-test"
            await pilot.click("#config-save")
            await pilot.pause()
        assert isinstance(app._llm_provider, OpenAIProvider)

    @pytest.mark.asyncio
    async def test_save_falls_back_to_dummy_when_fields_empty(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        app = self._create_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+shift+c")
            await pilot.pause()
            screen = app.screen
            screen.query_one("#config-url", Input).value = ""
            screen.query_one("#config-token", Input).value = ""
            await pilot.click("#config-save")
            await pilot.pause()
        assert isinstance(app._llm_provider, DummyLLMProvider)

    @pytest.mark.asyncio
    async def test_cancel_no_file_created(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        app = self._create_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+shift+c")
            await pilot.pause()
            await pilot.click("#config-cancel")
            await pilot.pause()
        assert not (tmp_path / "config.toml").exists()

    @pytest.mark.asyncio
    async def test_cancel_preserves_existing_config(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            'token = "sk-original"\n'
            'url = "https://original.com/v1"\n'
        )
        monkeypatch.chdir(tmp_path)
        app = self._create_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+shift+c")
            await pilot.pause()
            screen = app.screen
            screen.query_one("#config-url", Input).value = "https://changed.com/v1"
            await pilot.click("#config-cancel")
            await pilot.pause()
        content = config_path.read_text()
        assert "sk-original" in content
        assert "https://original.com/v1" in content
        assert "https://changed.com/v1" not in content

    @pytest.mark.asyncio
    async def test_fields_empty_when_no_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        app = self._create_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+shift+c")
            await pilot.pause()
            screen = app.screen
            assert screen.query_one("#config-url", Input).value == ""
            assert screen.query_one("#config-token", Input).value == ""
            assert screen.query_one("#config-model", Input).value == ""


class TestWordLimit:
    def test_trims_old_messages_when_limit_exceeded(self, history_repo):
        service = HistoryService(history_repo=history_repo, word_limit=5)
        service.add_message("one two three four five six", is_user=True)
        service.add_message("seven", is_user=False)
        assert len(service._chat) == 2
        service.add_message("eight nine ten eleven twelve", is_user=True)
        assert len(service._chat) <= 3
        texts = [m.text for m in service._chat]
        assert "one two three four five six" not in texts

    def test_unlimited_when_word_limit_zero(self, history_repo):
        service = HistoryService(history_repo=history_repo, word_limit=0)
        for i in range(20):
            service.add_message(f"message number {i} with some extra words", is_user=(i % 2 == 0))
            service.add_message("response", is_user=False)
        assert len(service._chat) == 40

    def test_load_chat_uses_load_recent_for_file_repo(self, tmp_path):
        from pychat_llm.repository import HistoryFileRepository
        import json
        repo = HistoryFileRepository(str(tmp_path / "history"))
        now = datetime.now()
        item = HistoryItem(id="test_chat", title="Test", created_at=now)
        repo.save(item)
        for i in range(10):
            repo.add_to_chat("test_chat", ChatMessage(id=i+1, text=f"message {i} word", is_user=(i % 2 == 0), created_at=now))
        service = HistoryService(history_repo=repo, word_limit=3)
        title, messages = service.load_chat("test_chat")
        assert len(messages) <= 3
        texts = [m.text for m in messages]
        assert "message 0 word" not in texts
        assert "message 9 word" in texts