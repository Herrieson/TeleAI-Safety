import json
from typing import Iterable

from benchmark.datasets.base import DatasetAdapter
from benchmark.schemas import Sample


class JsonlAdapter(DatasetAdapter):
    def load(self) -> Iterable[Sample]:
        path = self.config["path"]
        task = self.config.get("task", "default")
        field_map = self.config.get(
            "field_map",
            {"id": "id", "question": "question", "answer": "answer", "meta": "meta"},
        )
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                sample_id = str(row.get(field_map["id"], row.get("id", "")))
                question = row.get(field_map["question"], "")
                answer = row.get(field_map["answer"], "")
                meta = row.get(field_map.get("meta", "meta"), {})
                yield Sample(
                    id=sample_id,
                    task=row.get("task", task),
                    question=question,
                    answer=answer,
                    meta=meta,
                )
