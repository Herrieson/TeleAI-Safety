from typing import Any, List

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

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **_kwargs):
        return iterable

from telesafety_defense.base_factory import InputDefender, InferenceDefender, OutputDefender


def ensure_messages(payload: Any) -> List[dict]:
    if isinstance(payload, str):
        return [{"role": "user", "content": payload}]
    if isinstance(payload, list):
        return payload
    raise TypeError(f"Unsupported payload type for chat: {type(payload)}")


def batch_chat(model, queries: List[str], defenders: List = None, batch_size: int = 8) -> List[str]:
    """Process queries in batches with optional defenders."""
    responses = []

    for i in tqdm(range(0, len(queries), batch_size), desc="Processing batches"):
        batch_queries = queries[i:i + batch_size]
        batch_responses = []

        # Fast path: when no defenders are attached, delegate to model-native
        # batch inference if available.
        if not defenders and hasattr(model, "batch_chat"):
            try:
                batch_messages = [ensure_messages(query) for query in batch_queries]
                batch_responses = model.batch_chat(batch_messages, batch_size=len(batch_messages))
                if len(batch_responses) != len(batch_queries):
                    raise ValueError(
                        "model.batch_chat returned unexpected response count: "
                        f"{len(batch_responses)} != {len(batch_queries)}"
                    )
                responses.extend(batch_responses)
                continue
            except Exception as e:
                logger.warning(
                    "Falling back to per-sample chat because model.batch_chat failed: {}",
                    e,
                )

        for query in batch_queries:
            try:
                payload = query
                handled = False

                if defenders:
                    for defender in defenders:
                        if isinstance(defender, InputDefender):
                            payload = defender.defend(model, payload)
                            continue

                        if isinstance(defender, (OutputDefender, InferenceDefender)):
                            response = defender.defend(model, payload)
                            batch_responses.append(response)
                            handled = True
                            break

                        raise TypeError(
                            f"Unsupported defender type in runtime pipeline: {type(defender)}"
                        )
                    if handled:
                        continue

                messages = ensure_messages(payload)
                if hasattr(model, "chat"):
                    response = model.chat(messages=messages)
                    batch_responses.append(response)
                else:
                    raise AttributeError("Provided model does not support chat interface.")

            except Exception as e:
                logger.error(f"Error processing query: {e}")
                batch_responses.append("Error: Could not process request")

        responses.extend(batch_responses)

    return responses
