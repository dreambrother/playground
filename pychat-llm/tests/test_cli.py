from pychat_llm.cli import _create_llm_provider, _load_config
from pychat_llm.llm import DummyLLMProvider, OpenAIProvider


class TestLoadConfig:
    def test_returns_none_when_file_missing(self, tmp_path):
        result = _load_config(tmp_path / "nonexistent.toml")
        assert result is None

    def test_returns_openai_provider_with_valid_config(self, tmp_path):
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            'token = "sk-test"\n'
            'url = "http://localhost:8080/v1"\n'
        )
        result = _load_config(config_path)
        assert isinstance(result, OpenAIProvider)

    def test_returns_openai_provider_with_api_key_and_base_url_aliases(self, tmp_path):
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            'api_key = "sk-test"\n'
            'base_url = "http://localhost:8080/v1"\n'
            'model = "gpt-4"\n'
        )
        result = _load_config(config_path)
        assert isinstance(result, OpenAIProvider)
        assert result._model == "gpt-4"

    def test_returns_none_when_token_missing(self, tmp_path):
        config_path = tmp_path / "config.toml"
        config_path.write_text('url = "http://localhost:8080/v1"\n')
        assert _load_config(config_path) is None

    def test_returns_none_when_url_missing(self, tmp_path):
        config_path = tmp_path / "config.toml"
        config_path.write_text('token = "sk-test"\n')
        assert _load_config(config_path) is None


class TestCreateLLMProvider:
    def test_returns_openai_provider_when_config_present(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.toml"
        config_path.write_text('token = "sk-test"\nurl = "http://localhost:8080/v1"\n')
        monkeypatch.chdir(tmp_path)
        result = _create_llm_provider()
        assert isinstance(result, OpenAIProvider)

    def test_returns_dummy_provider_when_config_missing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = _create_llm_provider()
        assert isinstance(result, DummyLLMProvider)
