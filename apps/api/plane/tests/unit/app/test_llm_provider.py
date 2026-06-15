# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from plane.app.views.external import base


@pytest.mark.unit
class TestLLMConfig:
    def test_allows_custom_openai_compatible_model(self):
        with patch.object(
            base,
            "get_configuration_value",
            return_value=("test-key", "openai", "custom-model", "https://gateway.example/v1"),
        ):
            api_key, model, provider, base_url = base.get_llm_config()

        assert api_key == "test-key"
        assert model == "custom-model"
        assert provider == "openai"
        assert base_url == "https://gateway.example/v1"

    def test_missing_api_key_returns_empty_config(self):
        with patch.object(base, "get_configuration_value", return_value=("", "openai", "gpt-4o-mini", "")):
            api_key, model, provider, base_url = base.get_llm_config()

        assert api_key is None
        assert model is None
        assert provider is None
        assert base_url is None

    def test_missing_provider_returns_empty_config(self):
        with patch.object(base, "get_configuration_value", return_value=("test-key", "", "gpt-4o-mini", "")):
            api_key, model, provider, base_url = base.get_llm_config()

        assert api_key is None
        assert model is None
        assert provider is None
        assert base_url is None


@pytest.mark.unit
class TestOpenAICompatibleProvider:
    def test_openai_client_omits_base_url_when_empty(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="OpenAI response"))]
        )

        with patch.object(base, "OpenAI", return_value=mock_client) as mock_openai:
            response = base.get_openai_response("Prompt", "test-key", "custom-model", None)

        mock_openai.assert_called_once_with(api_key="test-key")
        mock_client.chat.completions.create.assert_called_once_with(
            model="custom-model",
            messages=[{"role": "user", "content": "Prompt"}],
        )
        assert response == "OpenAI response"

    def test_openai_client_uses_custom_base_url(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Gateway response"))]
        )

        with patch.object(base, "OpenAI", return_value=mock_client) as mock_openai:
            response = base.get_openai_response(
                "Prompt", "test-key", "custom-model", "https://gateway.example/v1"
            )

        mock_openai.assert_called_once_with(api_key="test-key", base_url="https://gateway.example/v1")
        assert response == "Gateway response"


@pytest.mark.unit
class TestAnthropicProvider:
    def test_anthropic_client_omits_base_url_when_empty(self):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = SimpleNamespace(content=[SimpleNamespace(text="Anthropic response")])

        with patch.object(base, "Anthropic", return_value=mock_client) as mock_anthropic:
            response = base.get_anthropic_response("Prompt", "test-key", "claude-3-5-sonnet-20241022", None)

        mock_anthropic.assert_called_once_with(api_key="test-key")
        mock_client.messages.create.assert_called_once_with(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=[{"role": "user", "content": "Prompt"}],
        )
        assert response == "Anthropic response"

    def test_anthropic_client_extracts_text_blocks(self):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = SimpleNamespace(
            content=[SimpleNamespace(text="First block"), SimpleNamespace(text="Second block")]
        )

        with patch.object(base, "Anthropic", return_value=mock_client) as mock_anthropic:
            response = base.get_anthropic_response(
                "Prompt", "test-key", "claude-3-5-sonnet-20241022", "https://anthropic-proxy.example"
            )

        mock_anthropic.assert_called_once_with(api_key="test-key", base_url="https://anthropic-proxy.example")
        mock_client.messages.create.assert_called_once_with(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=[{"role": "user", "content": "Prompt"}],
        )
        assert response == "First block\nSecond block"
