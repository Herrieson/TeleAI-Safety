import unittest
from unittest import mock

from telesafety_defense.config_loader import normalize_runtime_config


class ConfigLoaderTests(unittest.TestCase):
    def test_legacy_flat_config(self):
        cfg = {
            "max_new_tokens": 100,
            "temperature": 0.2,
            "do_sample": False,
            "backend": "local",
            "model_path": "./models/local",
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
        self.assertEqual(out.backend, "local")
        self.assertEqual(out.model_path, "./models/local")
        self.assertEqual(out.batch_size, 2)
        self.assertTrue(out.resume)
        self.assertEqual(out.checkpoint_every, 7)
        self.assertEqual(out.api["base_url"], "https://api.openai.com/v1")

    def test_nested_v2_config(self):
        cfg = {
            "generation": {"max_new_tokens": 300, "temperature": 0.5, "do_sample": True},
            "runtime": {
                "backend": "api",
                "batch_size": 8,
                "resume": False,
                "checkpoint_every": 0,
                "log_level": "DEBUG",
            },
            "dataset": {"attack_data_path": "./d", "attack_types": ["a"], "target_model": "tm"},
            "output": {"save_results_dir": "./o"},
            "api": {"provider": "azure", "base_url": "https://x.openai.azure.com", "deployment": "dep"},
        }
        out = normalize_runtime_config(cfg, "fallback")
        self.assertEqual(out.generation_config["max_new_tokens"], 300)
        self.assertEqual(out.backend, "api")
        self.assertIsNone(out.model_path)
        self.assertEqual(out.batch_size, 8)
        self.assertEqual(out.attack_data_path, "./d")
        self.assertEqual(out.save_dir, "./o")
        self.assertEqual(out.api["provider"], "azure")
        self.assertEqual(out.target_model, "tm")

    def test_model_path_from_env(self):
        cfg = {
            "runtime": {"backend": "local", "model_path_env": "TELESAFETY_MODEL_PATH"},
            "dataset": {"attack_data_path": "./d", "attack_types": ["a"], "target_model": "tm"},
            "output": {"save_results_dir": "./o"},
        }
        with mock.patch.dict("os.environ", {"TELESAFETY_MODEL_PATH": "/tmp/model-x"}, clear=False):
            out = normalize_runtime_config(cfg, None)
        self.assertEqual(out.model_path, "/tmp/model-x")

    def test_dataset_items_and_strict_exists(self):
        cfg = {
            "dataset": {
                "items": [
                    {"name": "gcg-local", "path": "./data/gcg.jsonl", "query_field": "prompt"},
                    {"path": "./data/other.jsonl"},
                ],
                "strict_exists": True,
            },
            "output": {"save_results_dir": "./o"},
        }
        out = normalize_runtime_config(cfg, None)
        self.assertTrue(out.strict_exists)
        self.assertEqual(len(out.dataset_items), 2)
        self.assertEqual(out.dataset_items[0]["name"], "gcg-local")
        self.assertEqual(out.dataset_items[0]["query_field"], "prompt")
        self.assertEqual(out.dataset_items[1]["path"], "./data/other.jsonl")


if __name__ == "__main__":
    unittest.main()
