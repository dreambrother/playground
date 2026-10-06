import tomllib
from datetime import datetime
from pathlib import Path
from typing import Callable

from pychat_llm.domain import HistoryItem
from pychat_llm.history import HistoryService
from pychat_llm.llm import DummyLLMProvider, LLMProvider, OpenAIProvider
from textual.app import App, ComposeResult
from textual.containers import Container, Right, Vertical, VerticalScroll
from textual.widgets import Button, Footer, Input, Label, ListItem, ListView, Markdown, Static, TextArea
from textual.binding import Binding
from textual.message import Message
from textual.screen import Screen


class ChatApp(App):
    CSS = """
    Screen {
        layout: vertical;
    }

    #chat-container {
        height: 1fr;
        padding: 1;
    }

    #header {
        dock: top;
        text-align: center;
        padding: 1;
        margin: 1 2 0 2;
        background: $panel;
        color: $text;
    }

    #input-container {
        height: auto;
        padding: 1;
        border-top: solid gray;
    }

    #message-input {
        width: 1fr;
        height: auto;
        max-height: 5;
    }

    #chat-list-title {
        text-align: center;
        padding: 1;
    }

    #no-chats {
        text-align: center;
        padding: 2;
        color: $text-muted;
    }

    #chat-list-view {
        height: 1fr;
        margin: 1 4;
        border: solid gray;
    }

    #cancel-chat-list {
        width: auto;
        margin: 1 4;
    }
    """

    BINDINGS = [
        Binding("ctrl+n", "new_chat", "New Chat", show=True),
        Binding("ctrl+o", "open_chat", "Open Chat", show=True),
        Binding("ctrl+shift+c", "open_config", "Config", show=True),
    ]

    def __init__(self, history_service: HistoryService, llm_provider: LLMProvider, **kwargs):
        super().__init__(**kwargs)
        self._history_service = history_service
        self._llm_provider = llm_provider

    def compose(self) -> ComposeResult:
        yield Static("PyChat LLM", id="header")
        yield Container(
            MessageContainer(id="messages"),
            id="chat-container",
        )
        yield Container(
            ChatInput(id="message-input", placeholder="Type a message... (Enter to send)"),
            id="input-container",
        )
        yield Footer()

    async def on_mount(self) -> None:
        self.query_one("#message-input", ChatInput).focus()
        await self.add_message(self._llm_provider.get_welcome_message(), is_user=False)

    def _create_bubble(self, text: str, is_user: bool = False, created_at: datetime | None = None, is_loading: bool = False) -> MessageBubble:
        bubble = MessageBubble(text, is_user=is_user, created_at=created_at, is_loading=is_loading)
        bubble.add_class("user" if is_user else "assistant")
        return bubble

    async def add_message(self, text: str, is_user: bool = False) -> None:
        msg = self._history_service.add_message(text, is_user)
        container = self.query_one("#messages", MessageContainer)
        bubble = self._create_bubble(text, is_user=is_user, created_at=msg.created_at)
        await container.mount(Right(bubble) if is_user else bubble)
        container.scroll_end(animate=False)

    def _add_message_sync(self, text: str, is_user: bool = False, created_at: datetime | None = None) -> None:
        container = self.query_one("#messages", MessageContainer)
        bubble = self._create_bubble(text, is_user=is_user, created_at=created_at)
        container.mount(Right(bubble) if is_user else bubble)
        container.scroll_end(animate=False)

    async def action_new_chat(self) -> None:
        self._history_service.new_chat()
        self._clear_messages()
        await self.add_message(self._llm_provider.get_welcome_message(), is_user=False)

    def action_open_chat(self) -> None:
        def on_dismiss(history_item: HistoryItem | None) -> None:
            if history_item:
                self._load_chat(history_item.id)
        chat_paths = self._history_service.list_chats()
        self.push_screen(ChatListScreen(chat_paths, self._history_service.get_chat_title), on_dismiss)

    def action_open_config(self) -> None:
        config_path = Path("config.toml")

        def on_dismiss(config: dict | None) -> None:
            if config and config.get("token") and config.get("url"):
                self._llm_provider = OpenAIProvider(
                    api_key=config["token"],
                    base_url=config["url"],
                    model=config.get("model", "gpt-4o-mini"),
                )
            else:
                self._llm_provider = DummyLLMProvider()

        self.push_screen(ConfigScreen(config_path), on_dismiss)

    def _load_chat(self, chat_id: str) -> None:
        title, messages = self._history_service.load_chat(chat_id)
        if not messages:
            return
        self._clear_messages()
        self.chat_title = title
        for message in messages:
            self._add_message_sync(message.text, is_user=message.is_user, created_at=message.created_at)

    def _clear_messages(self) -> None:
        container = self.query_one("#messages", MessageContainer)
        container.remove_children()
        self.chat_title = "Untitled"

    async def on_chat_input_submitted(self, event: ChatInput.Submitted) -> None:
        textarea = self.query_one("#message-input", ChatInput)
        text = textarea.text.strip()
        if not text:
            return
        textarea.text = ""
        await self.add_message(text, is_user=True)
        title, messages = self._history_service.get_chat()
        if len(messages) == 2:
            self.chat_title = title

        container = self.query_one("#messages", MessageContainer)
        placeholder = self._create_bubble("Thinking...", is_user=False, is_loading=True)
        await container.mount(placeholder)
        container.scroll_end(animate=False)

        response = await self._llm_provider.get_response(text, messages)

        msg = self._history_service.add_message(response, is_user=False)
        placeholder.set_text(response)
        placeholder.created_at = msg.created_at
        container.scroll_end(animate=False)


class ChatInput(TextArea):
    BINDINGS = [
        Binding("enter", "submit", "Submit", show=True, priority=True),
        Binding("ctrl+enter", "newline", "New line", show=True),
    ]

    def action_submit(self) -> None:
        self.post_message(self.Submitted(self))

    def action_newline(self) -> None:
        self.insert("\n")

    class Submitted(Message):
        def __init__(self, text_area: TextArea) -> None:
            super().__init__()
            self.text_area = text_area


class MessageBubble(Vertical):
    DEFAULT_CSS = """
    MessageBubble {
        width: auto;
        max-width: 80%;
        height: auto;
        padding: 1 2;
        margin-bottom: 1;
    }

    MessageBubble.user {
        background: $primary;
        color: $text;
    }

    MessageBubble.assistant {
        background: $surface;
        color: $text;
    }

    MessageBubble #bubble-content {
        width: auto;
        height: auto;
        max-width: 100%;
    }

    MessageBubble Markdown {
        padding: 0;
        background: transparent;
        max-width: 100%;
    }

    MessageBubble #bubble-time {
        text-align: right;
        color: $text-muted;
        padding-top: 1;
    }
    """

    LOADING_FRAMES = ["Думаю ⏳", "Думаю ⌛"]

    def __init__(self, text: str, is_user: bool = False, created_at: datetime | None = None, is_loading: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.text = text
        self.is_user = is_user
        self.is_loading = is_loading
        self._loading_index = 0
        self._timer = None
        self._created_at = None
        if created_at is not None:
            self._created_at = created_at

    @property
    def created_at(self) -> datetime | None:
        return self._created_at

    @created_at.setter
    def created_at(self, value: datetime | None) -> None:
        self._created_at = value
        if self.is_mounted:
            self._refresh_time()

    def compose(self) -> ComposeResult:
        if self.is_user:
            yield Static(self.text, id="bubble-content")
        else:
            yield Markdown(self.text, id="bubble-content")

    def on_mount(self) -> None:
        if self._created_at:
            self._refresh_time()
        if self.is_loading:
            self._timer = self.set_interval(0.5, self._update_loading)

    def _refresh_time(self) -> None:
        for widget in list(self.query("#bubble-time")):
            widget.remove()
        if self._created_at:
            now = datetime.now()
            if self._created_at.date() == now.date():
                time_str = self._created_at.strftime("%H:%M")
            else:
                time_str = self._created_at.strftime("%d.%m.%Y %H:%M")
            self.mount(Static(time_str, id="bubble-time"))

    def _update_loading(self) -> None:
        if not self.is_loading:
            if self._timer is not None:
                self._timer.stop()
            return
        self._loading_index = (self._loading_index + 1) % len(self.LOADING_FRAMES)
        self.text = self.LOADING_FRAMES[self._loading_index]
        content = self.query_one("#bubble-content")
        content.update(self.text)  # type: ignore[attr-defined]

    def set_text(self, text: str) -> None:
        self.text = text
        self.is_loading = False
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        content = self.query_one("#bubble-content")
        content.update(text)  # type: ignore[attr-defined]
        self.refresh(layout=True)


class MessageContainer(VerticalScroll):
    DEFAULT_CSS = """
    MessageContainer {
        height: 1fr;
        border: solid gray;
        padding: 1 2 1 1;
    }
    """


class ChatListScreen(Screen):
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
    ]

    def __init__(self, history_items: list[HistoryItem], load_chat_fn: Callable[[str], str], **kwargs):
        super().__init__(**kwargs)
        self._history_items = history_items
        self._load_chat_fn = load_chat_fn
        self._chat_items: dict[str, HistoryItem] = {}

    def compose(self) -> ComposeResult:
        yield Label("Select a chat to open:", id="chat-list-title")
        if not self._history_items:
            yield Label("No saved chats yet.", id="no-chats")
        else:
            items = []
            for item in self._history_items:
                title = self._load_chat_fn(item.id)
                date_str = item.created_at.strftime("%d.%m.%Y %H:%M")
                item_id = f"chat-list-item-{item.id}"
                self._chat_items[item_id] = item
                list_item = ListItem(Label(f"{date_str}  {title}"), id=item_id)
                items.append(list_item)
            yield ListView(*items, id="chat-list-view")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item.id:
            self.dismiss(self._chat_items[event.item.id])


class ConfigScreen(Screen):
    DEFAULT_CSS = """
    ConfigScreen {
        align: center middle;
    }

    #config-container {
        width: 50;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #config-title {
        text-align: center;
        padding: 1;
        background: $panel;
        width: 100%;
    }

    #config-form {
        padding: 1 0;
    }

    #config-form Label {
        padding: 1 0 0 0;
    }

    #config-buttons {
        padding: 1 0;
        align: center middle;
    }
    """

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Cancel"),
    ]

    def __init__(self, config_path: Path, **kwargs):
        super().__init__(**kwargs)
        self._config_path = config_path

    def compose(self) -> ComposeResult:
        with Container(id="config-container"):
            yield Label("Model Provider Configuration", id="config-title")
            with Container(id="config-form"):
                yield Label("API URL:")
                yield Input(placeholder="https://api.openai.com/v1", id="config-url")
                yield Label("Token:")
                yield Input(placeholder="sk-...", password=True, id="config-token")
                yield Label("Model:")
                yield Input(placeholder="gpt-4o-mini", id="config-model")
            with Container(id="config-buttons"):
                yield Button("Save", variant="primary", id="config-save")
                yield Button("Cancel", variant="default", id="config-cancel")

    def on_mount(self) -> None:
        config = self._read_config()
        if "url" in config:
            self.query_one("#config-url", Input).value = config["url"]
        if "token" in config:
            self.query_one("#config-token", Input).value = config["token"]
        if "model" in config:
            self.query_one("#config-model", Input).value = config["model"]

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "config-save":
            url = self.query_one("#config-url", Input).value.strip()
            token = self.query_one("#config-token", Input).value.strip()
            model = self.query_one("#config-model", Input).value.strip()
            config = {"url": url, "token": token, "model": model or "gpt-4o-mini"}
            self._write_config(config)
            self.dismiss(config)
        elif event.button.id == "config-cancel":
            self.dismiss(None)

    def _read_config(self) -> dict[str, str]:
        if not self._config_path.exists():
            return {}
        try:
            with open(self._config_path, "rb") as f:
                config = tomllib.load(f)
        except Exception:
            return {}
        result: dict[str, str] = {}
        token = config.get("token") or config.get("api_key")
        url = config.get("url") or config.get("base_url")
        model = config.get("model", "gpt-4o-mini")
        if token:
            result["token"] = token
        if url:
            result["url"] = url
        result["model"] = model
        return result

    def _write_config(self, config: dict[str, str]) -> None:
        lines = []
        lines.append(f'token = "{config["token"]}"')
        lines.append(f'url = "{config["url"]}"')
        lines.append(f'model = "{config["model"]}"')
        self._config_path.write_text("\n".join(lines) + "\n")
