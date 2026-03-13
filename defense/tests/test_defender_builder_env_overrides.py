import unittest
from unittest import mock

from telesafety_defense.defender_builder import create_defender_from_config


class _DummyDefender:
    def __init__(self, checkpoint_path="", model_name=""):
        self.checkpoint_path = checkpoint_path
        self.model_name = model_name


class DefenderBuilderEnvOverridesTests(unittest.TestCase):
    def test_top_level_env_override_sets_missing_value(self):
        cfg = {
            "defender_type": "DummyEnv",
            "checkpoint_path": "",
            "checkpoint_path_env": "JAILDAM_CHECKPOINT_PATH",
        }
        with mock.patch(
            "telesafety_defense.defender_builder.resolve_defender_class",
            return_value=_DummyDefender,
        ):
            with mock.patch.dict(
                "os.environ",
                {"JAILDAM_CHECKPOINT_PATH": "/tmp/jaildam.pt"},
                clear=False,
            ):
                defender = create_defender_from_config(cfg)
        self.assertEqual(defender.checkpoint_path, "/tmp/jaildam.pt")

    def test_top_level_env_override_does_not_override_explicit_value(self):
        cfg = {
            "defender_type": "DummyEnv",
            "checkpoint_path": "/explicit/value.pt",
            "checkpoint_path_env": "JAILDAM_CHECKPOINT_PATH",
        }
        with mock.patch(
            "telesafety_defense.defender_builder.resolve_defender_class",
            return_value=_DummyDefender,
        ):
            with mock.patch.dict(
                "os.environ",
                {"JAILDAM_CHECKPOINT_PATH": "/tmp/jaildam.pt"},
                clear=False,
            ):
                defender = create_defender_from_config(cfg)
        self.assertEqual(defender.checkpoint_path, "/explicit/value.pt")


if __name__ == "__main__":
    unittest.main()
