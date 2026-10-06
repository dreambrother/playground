import pytest
from unittest.mock import MagicMock, patch

from pychat_llm.domain import ChatMessage
from pychat_llm.llm import DummyLLMProvider, OpenAIProvider


class TestDummyLLMProvider:
    @pytest.mark.asyncio
    async def test_get_response_returns_one_of_predefined_strings(self):
        provider = DummyLLMProvider()
        response = await provider.get_response("hello", history=[])
        assert response in DummyLLMProvider.LLM_RESPONSES

    def test_get_welcome_message(self):
        provider = DummyLLMProvider()
        assert "dummy" in provider.get_welcome_message().lower()


class TestOpenAIProvider:
    @pytest.mark.asyncio
    async def test_get_response_returns_content_from_openai(self):
        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "OpenAI response"
        mock_client.chat.completions.create.return_value = mock_completion

        with patch("pychat_llm.llm.OpenAI", return_value=mock_client):
            provider = OpenAIProvider(api_key="test-key", base_url="http://localhost:8080/v1")
            response = await provider.get_response("hello", history=[])

        assert response == "OpenAI response"
        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "hello"}],
        )

    @pytest.mark.asyncio
    async def test_get_response_with_custom_model(self):
        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "Custom model response"
        mock_client.chat.completions.create.return_value = mock_completion

        with patch("pychat_llm.llm.OpenAI", return_value=mock_client):
            provider = OpenAIProvider(api_key="test-key", base_url="http://localhost:8080/v1", model="gpt-4")
            response = await provider.get_response("hello", history=[])

        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-4",
            messages=[{"role": "user", "content": "hello"}],
        )
        assert response == "Custom model response"

    @pytest.mark.asyncio
    async def test_get_response_includes_history(self):
        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "With context"
        mock_client.chat.completions.create.return_value = mock_completion

        history = [
            ChatMessage(id=1, text="Hi", is_user=True),
            ChatMessage(id=2, text="Hello", is_user=False),
        ]

        with patch("pychat_llm.llm.OpenAI", return_value=mock_client):
            provider = OpenAIProvider(api_key="test-key", base_url="http://localhost:8080/v1")
            response = await provider.get_response("How are you?", history=history)

        assert response == "With context"
        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello"},
                {"role": "user", "content": "How are you?"},
            ],
        )

    def test_get_welcome_message(self):
        provider = OpenAIProvider(api_key="test-key", base_url="http://localhost:8080/v1")
        assert "OpenAI" in provider.get_welcome_message()
