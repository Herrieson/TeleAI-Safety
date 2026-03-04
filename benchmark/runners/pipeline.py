import json
import os
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed

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
        num_workers = int(self.config.get("num_workers", 1))
        samples = list(self.dataset.load()) if num_workers > 1 else None
        dataset_iter = samples if samples is not None else self.dataset.load()
        progress_bar = None
        if self.config.get("progress_bar"):
            try:
                from tqdm import tqdm
            except ImportError:
                tqdm = None
            if tqdm is not None:
                total = self.config.get("progress_total")
                if total is None:
                    total = len(samples) if samples is not None else self._infer_progress_total()
                if num_workers > 1:
                    progress_bar = tqdm(total=total, desc="Evaluating", unit="sample")
                else:
                    dataset_iter = tqdm(dataset_iter, total=total, desc="Evaluating", unit="sample")
        if num_workers > 1:
            results_by_index = {}
            rows_by_index = {}
            def _process(sample: Sample):
                return self._process_sample(sample)

            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                future_map = {executor.submit(_process, sample): idx for idx, sample in enumerate(dataset_iter)}
                for future in as_completed(future_map):
                    idx = future_map[future]
                    judge_result, row = future.result()
                    results_by_index[idx] = judge_result
                    rows_by_index[idx] = row
                    processed += 1
                    if progress_bar is not None:
                        progress_bar.update(1)
                    if progress_every > 0 and processed % progress_every == 0:
                        print(f"Processed {processed} samples")
            for idx in sorted(results_by_index):
                results.append(results_by_index[idx])
                output_rows.append(rows_by_index[idx])
            if progress_bar is not None:
                progress_bar.close()
        else:
            for sample in dataset_iter:
                judge_result, row = self._process_sample(sample)
                results.append(judge_result)
                output_rows.append(row)
                processed += 1
                if progress_every > 0 and processed % progress_every == 0:
                    print(f"Processed {processed} samples")

        metric_result = self.metric.compute(results)
        self._write_outputs(output_rows, metric_result)
        if progress_every > 0:
            print(f"Processed {processed} samples (done)")
        return metric_result

    def _process_sample(self, sample: Sample):
        try:
            response = self.model.generate(sample.question)
        except Exception as exc:
            response = ModelResponse(
                text="",
                meta={
                    "error_stage": "model_generate",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            )
            judge_result = JudgeResult(
                score=0.0,
                label="model_error",
                rationale=str(exc),
                extra={
                    "error_stage": "model_generate",
                    "error_type": type(exc).__name__,
                },
            )
            return judge_result, self._build_row(sample, response, judge_result)

        try:
            judge_result = self.judge.score(sample, response)
        except Exception as exc:
            judge_result = JudgeResult(
                score=0.0,
                label="judge_error",
                rationale=str(exc),
                extra={
                    "error_stage": "judge_score",
                    "error_type": type(exc).__name__,
                },
            )
        return judge_result, self._build_row(sample, response, judge_result)

    def _infer_progress_total(self):
        dataset_cfg = self.config.get("dataset", {})
        dataset_type = dataset_cfg.get("type")
        path = dataset_cfg.get("path")
        if not path:
            return None
        try:
            if dataset_type == "csv":
                import csv

                with open(path, "r", encoding="utf-8-sig") as f:
                    reader = csv.reader(f)
                    next(reader, None)
                    return sum(1 for _ in reader)
            if dataset_type == "jsonl":
                with open(path, "r", encoding="utf-8") as f:
                    return sum(1 for line in f if line.strip())
        except OSError:
            return None
        return None

    def _build_row(
        self, sample: Sample, response: ModelResponse, judge_result: JudgeResult
    ) -> Dict:
        return {
            "id": sample.id,
            "task": sample.task,
            "question": sample.question,
            "answer": sample.answer,
            "response": response.text,
            "response_meta": response.meta,
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
