from typing import Any, Dict, List, Optional

try:
    from loguru import logger
except ImportError:
    import logging

    class _StdLoggerAdapter:
        def __init__(self, name: str):
            self._logger = logging.getLogger(name)

        @staticmethod
        def _format(msg, *args):
            if not args:
                return msg
            try:
                return msg.format(*args)
            except Exception:
                return f"{msg} | args={args}"

        def info(self, msg, *args):
            self._logger.info(self._format(msg, *args))

        def warning(self, msg, *args):
            self._logger.warning(self._format(msg, *args))

        def error(self, msg, *args):
            self._logger.error(self._format(msg, *args))

    logger = _StdLoggerAdapter(__name__)

from telesafety_defense.io_store import extract_queries, load_records, save_records
from telesafety_defense.resume_utils import load_existing_results, merge_existing_responses
from telesafety_defense.runtime_pipeline import batch_chat


def defend_chat(
    data_path: str,
    model,
    defenders: List = None,
    batch_size: int = 8,
    save_path: str = None,
    resume: bool = False,
    checkpoint_every: int = 0,
    query_field: Optional[str] = None,
) -> Dict[str, Any]:
    logger.info("Loading data from: {}", data_path)
    data = load_records(data_path)
    queries = extract_queries(data, query_field=query_field)

    if resume and save_path:
        existing = load_existing_results(save_path)
        data, restored = merge_existing_responses(data, existing)
        if restored > 0:
            logger.info(
                "Resume enabled: restored {} completed samples from {}",
                restored,
                save_path,
            )

    pending_indices = [idx for idx, row in enumerate(data) if "final_response" not in row]
    logger.info(
        "Processing {} pending queries (total: {})",
        len(pending_indices),
        len(queries),
    )

    def flush_results() -> None:
        if save_path:
            save_records(save_path, data)

    processed_since_flush = 0
    for start in range(0, len(pending_indices), batch_size):
        chunk_indices = pending_indices[start : start + batch_size]
        chunk_queries = [queries[i] for i in chunk_indices]
        chunk_responses = batch_chat(model, chunk_queries, defenders, batch_size=batch_size)
        chunk_responses = [response.strip() for response in chunk_responses]

        for row_index, response in zip(chunk_indices, chunk_responses):
            data[row_index]["final_response"] = response

        processed_since_flush += len(chunk_indices)
        if checkpoint_every and processed_since_flush >= checkpoint_every:
            flush_results()
            processed_since_flush = 0

    flush_results()
    if save_path:
        logger.info("Results saved to: {}", save_path)

    responses = [row.get("final_response", "") for row in data]
    return {
        "data": data,
        "queries": queries,
        "responses": responses,
        "save_path": save_path,
    }
