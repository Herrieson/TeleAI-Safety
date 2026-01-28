import json
import os
from typing import Dict, List

from benchmark.datasets import DatasetRegistry
from benchmark.judges import JudgeRegistry
from benchmark.metrics import MetricRegistry
from benchmark.models import ModelRegistry
from benchmark.schemas import JudgeResult, ModelResponse, Sample, MetricResult


class BenchmarkPipeline:
    def __init__(self, config: Dict):
        self.config = config
        dataset_cfg = config.get("dataset", {})
        model_cfg = config.get("model", {})
        judge_cfg = config.get("judge", {})
        metric_cfg = config.get("metric", {})

        self.dataset = DatasetRegistry.create(dataset_cfg["type"], dataset_cfg)
        self.model = ModelRegistry.create(model_cfg["type"], model_cfg)
        self.judge = JudgeRegistry.create(judge_cfg["type"], judge_cfg)
        self.metric = MetricRegistry.create(metric_cfg.get("type", "aggregate"), metric_cfg)

        self.output_path = config.get("output_path")
        self.summary_path = config.get("summary_path")

    def run(self) -> MetricResult:
        results: List[JudgeResult] = []
        output_rows = []
        progress_every = int(self.config.get("progress_every", 100))
        processed = 0
        for sample in self.dataset.load():
            response = self.model.generate(sample.question)
            judge_result = self.judge.score(sample, response)
            results.append(judge_result)
            output_rows.append(self._build_row(sample, response, judge_result))
            processed += 1
            if progress_every > 0 and processed % progress_every == 0:
                print(f"Processed {processed} samples")

        metric_result = self.metric.compute(results)
        self._write_outputs(output_rows, metric_result)
        if progress_every > 0:
            print(f"Processed {processed} samples (done)")
        return metric_result

    def _build_row(
        self, sample: Sample, response: ModelResponse, judge_result: JudgeResult
    ) -> Dict:
        return {
            "id": sample.id,
            "task": sample.task,
            "question": sample.question,
            "answer": sample.answer,
            "response": response.text,
            "judge": {
                "score": judge_result.score,
                "label": judge_result.label,
                "rationale": judge_result.rationale,
                "extra": judge_result.extra,
            },
            "meta": sample.meta,
        }

    def _write_outputs(self, rows: List[Dict], metric_result: MetricResult) -> None:
        if self.output_path:
            self._ensure_parent_dir(self.output_path)
            with open(self.output_path, "w", encoding="utf-8") as f:
                for row in rows:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
        if self.summary_path:
            self._ensure_parent_dir(self.summary_path)
            with open(self.summary_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(metric_result.__dict__, ensure_ascii=False, indent=2))

    def _ensure_parent_dir(self, path: str) -> None:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
