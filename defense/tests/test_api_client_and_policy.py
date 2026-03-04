import json
import unittest
from unittest import mock

from telesafety_defense.api_client import OpenAICompatibleChatClient
from telesafety_defense.backend_policy import (
    DEFAULT_API_ALLOWED_DEFENDER_CLASSES,
    validate_api_defender_compatibility,
)


class _FakeHTTPResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyDefender:
    pass


class PassThroughDefender:
    pass


class APIClientAndPolicyTests(unittest.TestCase):
    def test_openai_request_shape(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = {k.lower(): v for k, v in request.header_items()}
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return _FakeHTTPResponse(
                {"choices": [{"message": {"content": "ok-openai"}}]}
            )

        client = OpenAICompatibleChatClient(
            model_name="gpt-4o-mini",
            api_key="k",
            base_url="https://api.openai.com/v1",
            provider="openai",
        )
        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            text = client.chat(
                [{"role": "user", "content": "hi"}],
                max_new_tokens=32,
                temperature=0.2,
                top_p=0.9,
            )

        self.assertEqual(text, "ok-openai")
        self.assertEqual(captured["url"], "https://api.openai.com/v1/chat/completions")
        self.assertIn("authorization", captured["headers"])
        self.assertEqual(captured["body"]["model"], "gpt-4o-mini")
        self.assertEqual(captured["body"]["max_tokens"], 32)

    def test_azure_request_shape(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = {k.lower(): v for k, v in request.header_items()}
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return _FakeHTTPResponse(
                {"choices": [{"message": {"content": "ok-azure"}}]}
            )

        client = OpenAICompatibleChatClient(
            model_name="unused-on-azure",
            api_key="k",
            base_url="https://example.openai.azure.com",
            provider="azure",
            deployment="dep-1",
            api_version="2024-12-01-preview",
        )
        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            text = client.chat([{"role": "user", "content": "hi"}], max_new_tokens=16)

        self.assertEqual(text, "ok-azure")
        self.assertIn("/openai/deployments/dep-1/chat/completions", captured["url"])
        self.assertIn("api-version=2024-12-01-preview", captured["url"])
        self.assertIn("api-key", captured["headers"])
        self.assertNotIn("model", captured["body"])
        self.assertEqual(captured["body"]["max_tokens"], 16)

    def test_api_policy_rejects_unsupported(self):
        defenders = [PassThroughDefender(), _DummyDefender()]
        with self.assertRaises(ValueError):
            validate_api_defender_compatibility(defenders)

    def test_api_policy_accepts_allowed(self):
        defenders = [PassThroughDefender()]
        validate_api_defender_compatibility(
            defenders, allowed_classes=DEFAULT_API_ALLOWED_DEFENDER_CLASSES
        )

    def test_api_policy_rejects_non_api_defender_type(self):
        defenders = [PassThroughDefender()]
        with self.assertRaises(ValueError):
            validate_api_defender_compatibility(
                defenders,
                allowed_classes=DEFAULT_API_ALLOWED_DEFENDER_CLASSES,
                defender_type="DRO",
            )


if __name__ == "__main__":
    unittest.main()
