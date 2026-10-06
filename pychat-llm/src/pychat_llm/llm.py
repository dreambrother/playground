import asyncio
from abc import ABC, abstractmethod
from random import choice

from openai import OpenAI
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionUserMessageParam,
)

from pychat_llm.domain import ChatMessage


class LLMProvider(ABC):
    @abstractmethod
    async def get_response(self, prompt: str, history: list[ChatMessage]) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_welcome_message(self) -> str:
        raise NotImplementedError


class DummyLLMProvider(LLMProvider):
    LLM_RESPONSES = [
        "Интересный вопрос! Дайте подумать...",
        "Понимаю вашу обеспокоенность. Вот что могу сказать.",
        "Отличная мысль! Вот мой взгляд на эту тему.",
        "Исходя из моих знаний, вот что могу поделиться.",
        "Это сложная тема. Позвольте разложить её по полочкам.",
        "Спасибо за вопрос. Вот подробный ответ.",
        "Вот что я думаю — это зависит от нескольких факторов.",
        "Интересно! Позвольте дать немного контекста.",
        "С радостью помогу. Вот моё мнение на этот счёт.",
        "Распространённый вопрос. Вот развёрнутый ответ.",
    ]

    async def get_response(self, prompt: str, history: list[ChatMessage]) -> str:
        return choice(DummyLLMProvider.LLM_RESPONSES)

    def get_welcome_message(self) -> str:
        return "Привет! Это dummy AI-ассистент. Чем могу помочь?"


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, base_url: str, model: str = "gpt-4o-mini"):
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    async def get_response(self, prompt: str, history: list[ChatMessage]) -> str:
        messages: list[ChatCompletionMessageParam] = []
        for msg in history:
            if msg.is_user:
                messages.append(ChatCompletionUserMessageParam(role="user", content=msg.text))
            else:
                messages.append(ChatCompletionAssistantMessageParam(role="assistant", content=msg.text))
        messages.append(ChatCompletionUserMessageParam(role="user", content=prompt))

        response = await asyncio.to_thread(
            self._client.chat.completions.create,
            model=self._model,
            messages=messages,
        )
        return response.choices[0].message.content or ""

    def get_welcome_message(self) -> str:
        return "Привет! Я ваш AI-ассистент на базе OpenAI. Чем могу помочь?"
