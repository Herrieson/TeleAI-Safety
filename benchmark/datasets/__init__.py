from benchmark.datasets.base import DatasetAdapter
from benchmark.datasets.registry import DatasetRegistry
from benchmark.datasets.jsonl_adapter import JsonlAdapter
from benchmark.datasets.csv_adapter import CsvAdapter
from benchmark.datasets.hf_adapter import HuggingFaceAdapter

DatasetRegistry.register("jsonl", JsonlAdapter)
DatasetRegistry.register("csv", CsvAdapter)
DatasetRegistry.register("hf", HuggingFaceAdapter)

__all__ = ["DatasetAdapter", "DatasetRegistry"]
