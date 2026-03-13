import unittest
from importlib.util import find_spec

from telesafety_defense.defender_builder import create_defender
from telesafety_defense.defender_registry import list_registered_defenders, resolve_defender_class


class DefenderRegistryBuilderTests(unittest.TestCase):
    def test_registry_has_passthrough(self):
        self.assertIn("PassThrough", list_registered_defenders())
        cls = resolve_defender_class("PassThrough")
        self.assertEqual(cls.__name__, "PassThroughDefender")

    def test_create_defender_passthrough(self):
        defender = create_defender("PassThrough")
        self.assertEqual(defender.__class__.__name__, "PassThroughDefender")

    def test_registry_has_new_defenders(self):
        names = list_registered_defenders()
        self.assertIn("LLMLingua", names)
        self.assertIn("JailDAM", names)
        self.assertIn("DPS", names)
        self.assertIn("CourtGuard", names)

    @unittest.skipUnless(find_spec("torch") is not None, "torch is required for JailDAM import")
    def test_create_jaildam_defender(self):
        defender = create_defender("JailDAM", checkpoint_path="")
        self.assertEqual(defender.__class__.__name__, "JailDAMDefender")

    def test_create_llmlingua_defender_without_strict_init(self):
        defender = create_defender("LLMLingua", strict_init=False)
        self.assertEqual(defender.__class__.__name__, "LLMLinguaDefender")

    @unittest.skipUnless(find_spec("PIL") is not None, "Pillow is required for DPS import")
    def test_create_dps_defender(self):
        defender = create_defender("DPS")
        self.assertEqual(defender.__class__.__name__, "DPSDefender")

    def test_create_courtguard_defender(self):
        defender = create_defender(
            "CourtGuard",
            detector_backend={
                "type": "local_transformers",
                "model_path": "dummy-model-path",
                "device": "cpu",
            },
            detector_type="direct",
        )
        self.assertEqual(defender.__class__.__name__, "CourtGuardDefender")

    def test_create_rpo_defender_without_local_model(self):
        defender = create_defender("RPO")
        self.assertEqual(defender.__class__.__name__, "RPODefender")

    def test_create_erasecheck_defender_without_local_model(self):
        defender = create_defender("EraseCheck")
        self.assertEqual(defender.__class__.__name__, "EraseCheckDefender")

    def test_unknown_defender_raises(self):
        with self.assertRaises(ValueError):
            resolve_defender_class("NotARealDefender")


if __name__ == "__main__":
    unittest.main()
