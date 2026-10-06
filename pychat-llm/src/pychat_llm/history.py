from datetime import datetime

from pychat_llm.domain import ChatMessage, HistoryItem
from pychat_llm.repository import HistoryRepository


class HistoryService:
    def __init__(self, history_repo: HistoryRepository, word_limit: int = 10000):
        self._message_seq = 1
        self._chat: list[ChatMessage] = []
        self._history_repo = history_repo
        self._current_chat_id: str | None = None
        self._word_limit = word_limit

    def add_message(self, text: str, is_user: bool) -> ChatMessage:
        item = ChatMessage(id=self._next_id(), text=text, is_user=is_user)
        self._chat.append(item)
        self._persist_if_needed(item)
        self._trim_chat()
        return item

    def list_chats(self) -> list[HistoryItem]:
        chats = self._history_repo.list_chats()
        chats.sort(key=lambda item: item.created_at, reverse=True)
        return chats

    def load_chat(self, chat_id: str) -> tuple[str, list[ChatMessage]]:
        if self._word_limit > 0:
            chat = self._history_repo.load_recent(chat_id, self._word_limit)
        else:
            chat = self._history_repo.load(chat_id)
        self._chat = list(chat)
        if self._chat:
            self._message_seq = max(m.id for m in self._chat) + 1
        else:
            self._message_seq = 1
        self._current_chat_id = chat_id
        return self._get_chat_title(self._chat), self._chat

    def get_chat(self, chat_id: str | None = None) -> tuple[str, list[ChatMessage]]:
        if chat_id:
            chat = self._history_repo.load(chat_id)
        else:
            chat = self._chat
        return self._get_chat_title(chat), chat

    def get_chat_title(self, chat_id: str) -> str:
        return self._get_chat_title(self._history_repo.load(chat_id))

    def new_chat(self) -> None:
        self._chat = []
        self._message_seq = 1
        self._current_chat_id = None

    def _next_id(self) -> int:
        new_id = self._message_seq
        self._message_seq += 1
        return new_id

    def _persist_if_needed(self, latest_message: ChatMessage) -> None:
        if len(self._chat) < 2:
            return
        if self._current_chat_id is None:
            chat_id = self._chat_id()
            self._current_chat_id = chat_id
            self._history_repo.save(HistoryItem(
                id=chat_id,
                title=self._get_chat_title(self._chat),
                created_at=self._chat_created_at(),
            ))
            self._history_repo.add_to_chat(chat_id, *self._chat)
        else:
            self._history_repo.add_to_chat(self._current_chat_id, latest_message)

    def _is_first_user_message(self) -> bool:
        return len(self._chat) == 2

    def _chat_id(self) -> str:
        return self._chat_created_at().strftime("%d%m%y-%H%M%S")

    def _chat_created_at(self) -> datetime:
        return self._chat[0].created_at

    def _get_chat_title(self, chat: list[ChatMessage]) -> str:
        if not self._has_user_message(chat):
            return ""
        return (chat[1:2])[0].text[:30]

    def _has_user_message(self, chat: list[ChatMessage]) -> bool:
        return any(item.is_user for item in chat)

    def _trim_chat(self) -> None:
        if self._word_limit <= 0:
            return
        total = 0
        keep_idx = 0
        for i in range(len(self._chat) - 1, -1, -1):
            total += len(self._chat[i].text.split())
            if total >= self._word_limit:
                keep_idx = i
                break
        if keep_idx > 0 and len(self._chat) > keep_idx:
            self._chat = self._chat[keep_idx:]