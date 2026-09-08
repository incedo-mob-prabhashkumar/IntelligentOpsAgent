from __future__ import annotations

import os
import unittest

from src.config import get_settings


class OpenAIConfigTests(unittest.TestCase):
    def test_openai_settings_are_loaded_from_environment(self) -> None:
        os.environ["LLM_PROVIDER"] = "openai"
        os.environ["OPENAI_API_KEY"] = "sk-test-key"
        os.environ["OPENAI_MODEL"] = "gpt-4o-mini"
        os.environ["OPENAI_BASE_URL"] = "https://api.openai.com/v1"

        try:
            settings = get_settings()
            self.assertEqual(settings.llm_provider, "openai")
            self.assertEqual(settings.openai_api_key, "sk-test-key")
            self.assertEqual(settings.openai_model, "gpt-4o-mini")
            self.assertEqual(settings.openai_base_url, "https://api.openai.com/v1")
        finally:
            os.environ.pop("LLM_PROVIDER", None)
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("OPENAI_MODEL", None)
            os.environ.pop("OPENAI_BASE_URL", None)

    def test_llama_settings_are_loaded_from_environment(self) -> None:
        os.environ["LLM_PROVIDER"] = "llama"
        os.environ["LLAMA_API_KEY"] = "dummy-key"
        os.environ["LLAMA_MODEL"] = "llama3.1:8b"
        os.environ["LLAMA_BASE_URL"] = "http://localhost:8080/v1"

        try:
            settings = get_settings()
            self.assertEqual(settings.llm_provider, "llama")
            self.assertEqual(settings.llama_api_key, "dummy-key")
            self.assertEqual(settings.llama_model, "llama3.1:8b")
            self.assertEqual(settings.llama_base_url, "http://localhost:8080/v1")
        finally:
            os.environ.pop("LLM_PROVIDER", None)
            os.environ.pop("LLAMA_API_KEY", None)
            os.environ.pop("LLAMA_MODEL", None)
            os.environ.pop("LLAMA_BASE_URL", None)


if __name__ == "__main__":
    unittest.main()
