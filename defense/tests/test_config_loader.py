import unittest

from telesafety_defense.config_loader import normalize_runtime_config


class ConfigLoaderTests(unittest.TestCase):
    def test_legacy_flat_config(self):
        cfg = {
            "max_new_tokens": 100,
            "temperature": 0.2,
            "do_sample": False,
            "attack_data_path": "./a",
            "attack_types": ["x"],
            "target_model": "m",
            "batch_size": 2,
            "save_results_dir": "./r",
            "resume": True,
            "checkpoint_every": 7,
            "api_base_url": "https://api.openai.com/v1",
            "api_model_name": "gpt",
        }
        out = normalize_runtime_config(cfg, None)
        self.assertEqual(out.generation_config["max_new_tokens"], 100)
        self.assertEqual(out.attack_types, ["x"])
        self.assertEqual(out.batch_size, 2)
        self.assertTrue(out.resume)
        self.assertEqual(out.checkpoint_every, 7)
        self.assertEqual(out.api["base_url"], "https://api.openai.com/v1")

    def test_nested_v2_config(self):
        cfg = {
            "generation": {"max_new_tokens": 300, "temperature": 0.5, "do_sample": True},
            "runtime": {"batch_size": 8, "resume": False, "checkpoint_every": 0, "log_level": "DEBUG"},
            "dataset": {"attack_data_path": "./d", "attack_types": ["a"], "target_model": "tm"},
            "output": {"save_results_dir": "./o"},
            "api": {"provider": "azure", "base_url": "https://x.openai.azure.com", "deployment": "dep"},
        }
        out = normalize_runtime_config(cfg, "fallback")
        self.assertEqual(out.generation_config["max_new_tokens"], 300)
        self.assertEqual(out.batch_size, 8)
        self.assertEqual(out.attack_data_path, "./d")
        self.assertEqual(out.save_dir, "./o")
        self.assertEqual(out.api["provider"], "azure")
        self.assertEqual(out.target_model, "tm")


if __name__ == "__main__":
    unittest.main()
