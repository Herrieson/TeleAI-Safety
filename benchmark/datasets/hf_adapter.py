from typing import Iterable

from benchmark.datasets.base import DatasetAdapter
from benchmark.schemas import Sample


class HuggingFaceAdapter(DatasetAdapter):
    def load(self) -> Iterable[Sample]:
        try:
            from datasets import load_dataset
        except ImportError as exc:
            raise ImportError("datasets is required for HuggingFaceAdapter") from exc

        name = self.config["name"]
        split = self.config.get("split", "train")
        task = self.config.get("task", "default")
        task_field = self.config.get("task_field")
        field_map = self.config.get(
            "field_map",
            {"id": "id", "question": "question", "answer": "answer", "meta": "meta"},
        )
        ds = load_dataset(name, split=split)
        for row in ds:
            sample_id = str(row.get(field_map["id"], row.get("id", "")))
            question = row.get(field_map["question"], "")
            answer = row.get(field_map["answer"], "")
            meta = row.get(field_map.get("meta", "meta"), {})
            row_task = row.get(task_field, task) if task_field else row.get("task", task)
            yield Sample(
                id=sample_id,
                task=row_task,
                question=question,
                answer=answer,
                meta=meta,
            )
