import unittest

from telesafety_defense.methods.semanticsmoothllm import SemanticSmoothLLMDefender
from telesafety_defense.methods.smoothllm import SmoothLLMDefender


class _AlwaysJailbreakScorer:
    def score(self, query=None, response=""):
        return {"score": 1}


class _ChatOnlyModel:
    def __init__(self):
        self.calls = []

    def chat(self, messages, **_kwargs):
        content = messages[-1]["content"]
        self.calls.append(content)
        if isinstance(content, str) and "Now paraphrase the instruction in the input." in content:
            return '{"paraphrase":"SAFE"}'
        return f"RESP:{content}"


class SmoothMethodsAPIFallbackTests(unittest.TestCase):
    def test_smoothllm_falls_back_to_per_sample_chat(self):
        model = _ChatOnlyModel()
        defender = SmoothLLMDefender(
            model=object(),
            model_name="dummy",
            tokenizer=object(),
            scorer=_AlwaysJailbreakScorer(),
            pert_type="RandomSwapPerturbation",
            pert_pct=0.0,
            num_copies=3,
            batch_size=2,
        )
        response = defender.defend(model, [{"role": "user", "content": "hello"}])
        self.assertEqual(response, "RESP:hello")
        self.assertEqual(len(model.calls), 3)

    def test_semanticsmoothllm_falls_back_to_per_sample_chat(self):
        model = _ChatOnlyModel()
        defender = SemanticSmoothLLMDefender(
            model=object(),
            model_name="dummy",
            tokenizer=object(),
            scorer=_AlwaysJailbreakScorer(),
            pert_type="paraphrase",
            num_samples=2,
            batch_size=2,
        )
        response = defender.defend(model, [{"role": "user", "content": "hello"}])
        self.assertEqual(response, "RESP:SAFE")
        self.assertEqual(len(model.calls), 4)
        self.assertTrue(any("In this task, you will receive an english instruction." in c for c in model.calls))
        self.assertFalse(any(c == "PARAPHRASE_TEXT" for c in model.calls))


if __name__ == "__main__":
    unittest.main()
