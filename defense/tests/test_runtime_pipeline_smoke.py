import unittest

from telesafety_defense.base_factory import InputDefender, OutputDefender, TrainingDefender
from telesafety_defense.runtime_pipeline import batch_chat


class _DummyModel:
    def __init__(self):
        self.calls = 0

    def chat(self, messages):
        self.calls += 1
        return f"MODEL:{messages[-1]['content']}"


class _DummyBatchModel(_DummyModel):
    def __init__(self):
        super().__init__()
        self.batch_calls = 0

    def batch_chat(self, batch_messages, batch_size=8, **_kwargs):
        self.batch_calls += 1
        return [f"BATCH:{messages[-1]['content']}" for messages in batch_messages]


class _PrefixInputDefender(InputDefender):
    def defend(self, model, messages):
        if isinstance(messages, str):
            return [{"role": "user", "content": f"[SAFE]{messages}"}]
        patched = [msg.copy() for msg in messages]
        patched[-1]["content"] = f"[SAFE]{patched[-1]['content']}"
        return patched


class _FixedOutputDefender(OutputDefender):
    def defend(self, model, messages):
        return "BLOCKED"


class _DummyTrainingDefender(TrainingDefender):
    def defend(self, model=None, messages=None):
        return "./fake-trained-model"


class RuntimePipelineSmokeTests(unittest.TestCase):
    def test_no_defender_prefers_batch_chat(self):
        model = _DummyBatchModel()
        responses = batch_chat(model, ["hello", "world"], defenders=None, batch_size=2)
        self.assertEqual(responses, ["BATCH:hello", "BATCH:world"])
        self.assertEqual(model.batch_calls, 1)
        self.assertEqual(model.calls, 0)

    def test_input_defender_then_model_generation(self):
        model = _DummyModel()
        defenders = [_PrefixInputDefender()]
        responses = batch_chat(model, ["hello"], defenders=defenders, batch_size=1)
        self.assertEqual(responses, ["MODEL:[SAFE]hello"])
        self.assertEqual(model.calls, 1)

    def test_output_defender_short_circuits_model(self):
        model = _DummyModel()
        defenders = [_FixedOutputDefender()]
        responses = batch_chat(model, ["hello"], defenders=defenders, batch_size=1)
        self.assertEqual(responses, ["BLOCKED"])
        self.assertEqual(model.calls, 0)

    def test_training_defender_contract(self):
        trainer = _DummyTrainingDefender()
        checkpoint = trainer.defend()
        self.assertEqual(checkpoint, "./fake-trained-model")


if __name__ == "__main__":
    unittest.main()
