import tempfile
import unittest
from pathlib import Path
from unittest import mock

from telesafety_defense.methods.guardreasoner import GuardReasonerDefender
from telesafety_defense.utils import SORRY_RESPONSE


class _SequenceChatModel:
    def __init__(self, outputs):
        self._outputs = list(outputs)
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append({"messages": messages, "kwargs": kwargs})
        if not self._outputs:
            return ""
        return self._outputs.pop(0)


class GuardReasonerBackendTests(unittest.TestCase):
    def test_runtime_model_backend_blocks_harmful(self):
        model = _SequenceChatModel(
            [
                "base answer",
                "Request: harmful\nResponse: benign\nReasoning: blocked",
            ]
        )
        defender = GuardReasonerDefender(
            guard_backend="runtime_model",
            sampling_kwargs={"max_tokens": 16, "temperature": 0.0},
        )
        out = defender.defend(model, [{"role": "user", "content": "question"}])
        self.assertEqual(out, SORRY_RESPONSE)
        self.assertEqual(len(model.calls), 2)
        self.assertEqual(model.calls[1]["kwargs"].get("max_new_tokens"), 16)

    def test_runtime_model_backend_allows_benign(self):
        model = _SequenceChatModel(
            [
                "base answer",
                "Request: benign\nResponse: benign\nReasoning: safe",
            ]
        )
        defender = GuardReasonerDefender(guard_backend="runtime_model")
        out = defender.defend(model, [{"role": "user", "content": "question"}])
        self.assertEqual(out, "base answer")

    def test_guard_template_path_is_used(self):
        model = _SequenceChatModel(
            [
                "base answer",
                "Request: benign\nResponse: benign",
            ]
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / "guard_template.txt"
            template_path.write_text("CUSTOM TEMPLATE\nQ={prompt}\nA={response}\n", encoding="utf-8")
            defender = GuardReasonerDefender(
                guard_backend="runtime_model",
                guard_template_path=str(template_path),
            )
            out = defender.defend(model, [{"role": "user", "content": "q"}])
        self.assertEqual(out, "base answer")
        guard_prompt = model.calls[1]["messages"][0]["content"]
        self.assertIn("CUSTOM TEMPLATE", guard_prompt)

    def test_api_backend_uses_openai_compatible_client(self):
        model = _SequenceChatModel(["base answer"])

        class _FakeClient:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                self.messages = None

            def chat(self, messages, **kwargs):
                self.messages = messages
                self.chat_kwargs = kwargs
                return "Request: harmful\nResponse: benign"

        fake_client = _FakeClient()

        with mock.patch(
            "telesafety_defense.methods.guardreasoner.OpenAICompatibleChatClient",
            autospec=True,
        ) as mocked_client_cls:
            mocked_client_cls.return_value = fake_client
            defender = GuardReasonerDefender(
                guard_backend="api",
                guard_backend_config={
                    "provider": "openai",
                    "base_url": "https://api.openai.com/v1",
                    "model_name": "gpt-4o-mini",
                    "key": "k",
                },
            )
            out = defender.defend(model, [{"role": "user", "content": "q"}])

        self.assertEqual(out, SORRY_RESPONSE)
        mocked_client_cls.assert_called_once()
        self.assertIsNotNone(fake_client.messages)
        self.assertEqual(fake_client.messages[0]["role"], "system")


if __name__ == "__main__":
    unittest.main()
