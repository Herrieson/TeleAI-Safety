import unittest
from types import SimpleNamespace
from unittest import mock

from telesafety_defense.run_defense import _build_eval_jobs, _build_model_and_defenders


class _DummyDefender:
    pass


class RunDefenseBackendSelectionTests(unittest.TestCase):
    def _runtime_cfg(self, **overrides):
        cfg = {
            "backend": "auto",
            "model_path": None,
            "target_model": "dummy-target",
            "attack_types": ["gcg"],
            "attack_data_path": "./attack_results",
            "dataset_items": [],
            "strict_exists": False,
            "save_dir": "./results",
            "generation_config": {"max_new_tokens": 32},
            "api": {},
        }
        cfg.update(overrides)
        return SimpleNamespace(**cfg)

    def test_auto_mode_allows_defender_native_backend(self):
        runtime_cfg = self._runtime_cfg(backend="auto", api={})
        defender = _DummyDefender()
        model, defenders = _build_model_and_defenders(
            defender,
            {"defender_type": "CourtGuard"},
            runtime_cfg,
        )
        self.assertIsNone(model)
        self.assertEqual(defenders, [defender])

    def test_auto_mode_rejects_missing_pipeline_model_when_required(self):
        runtime_cfg = self._runtime_cfg(backend="auto", api={})
        defender = _DummyDefender()
        with self.assertRaises(ValueError):
            _build_model_and_defenders(
                defender,
                {"defender_type": "DPS"},
                runtime_cfg,
            )

    def test_auto_mode_prefers_local_model_path(self):
        runtime_cfg = self._runtime_cfg(
            backend="auto",
            model_path="./models/local",
            api={
                "base_url": "https://api.openai.com/v1",
                "model_name": "gpt-4o-mini",
                "key": "k",
            },
        )
        defender = _DummyDefender()
        with mock.patch("telesafety_defense.run_defense._load_model", return_value="LOCAL") as mocked_load:
            model, defenders = _build_model_and_defenders(
                defender,
                {"defender_type": "DPS", "model_name": "dummy-model"},
                runtime_cfg,
            )
        self.assertEqual(model, "LOCAL")
        self.assertEqual(defenders, [defender])
        mocked_load.assert_called_once()
        self.assertEqual(mocked_load.call_args.kwargs["model_path"], "./models/local")

    def test_api_mode_uses_api_backend(self):
        runtime_cfg = self._runtime_cfg(
            backend="api",
            api={
                "base_url": "https://api.openai.com/v1",
                "model_name": "gpt-4o-mini",
                "key": "k",
                "provider": "openai",
                "allowed_defenders": ["_DummyDefender"],
            },
        )
        defender = _DummyDefender()
        with mock.patch("telesafety_defense.run_defense._load_model", return_value="API") as mocked_load:
            with mock.patch(
                "telesafety_defense.run_defense.validate_api_defender_compatibility"
            ) as mocked_policy:
                model, defenders = _build_model_and_defenders(
                    defender,
                    {"defender_type": "LLMLingua"},
                    runtime_cfg,
                )
        self.assertEqual(model, "API")
        self.assertEqual(defenders, [defender])
        mocked_load.assert_called_once()
        mocked_policy.assert_called_once()

    def test_build_eval_jobs_prefers_explicit_items(self):
        runtime_cfg = self._runtime_cfg(
            dataset_items=[
                {
                    "name": "custom-gcg",
                    "path": "./datasets/gcg.jsonl",
                    "query_field": "question",
                    "output_name": "my_output",
                }
            ],
            save_dir="./save",
        )
        jobs = _build_eval_jobs(runtime_cfg, defender_type="CourtGuard")
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["name"], "custom-gcg")
        self.assertEqual(jobs[0]["data_path"], "./datasets/gcg.jsonl")
        self.assertEqual(jobs[0]["query_field"], "question")
        self.assertEqual(jobs[0]["save_path"], "./save/my_output_CourtGuard.json")

    def test_build_eval_jobs_legacy_fallback(self):
        runtime_cfg = self._runtime_cfg(
            dataset_items=[],
            attack_types=["gcg", "scav"],
            attack_data_path="./attack_results",
            target_model="vicuna-7b-v1.5",
            save_dir="./save",
        )
        jobs = _build_eval_jobs(runtime_cfg, defender_type="DPS")
        self.assertEqual(len(jobs), 2)
        self.assertEqual(
            jobs[0]["data_path"],
            "./attack_results/gcg_vicuna-7b-v1.5.jsonl",
        )
        self.assertEqual(
            jobs[0]["save_path"],
            "./save/gcg_vicuna-7b-v1.5_DPS.json",
        )


if __name__ == "__main__":
    unittest.main()
