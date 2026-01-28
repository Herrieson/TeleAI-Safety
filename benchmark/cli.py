import argparse
import json
import os
import re

from benchmark.runners import BenchmarkPipeline


def load_config(path: str) -> dict:
    if path.endswith(".json"):
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return _expand_env_vars(config)
    try:
        import yaml
    except ImportError as exc:
        raise ImportError("PyYAML is required for YAML configs") from exc
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return _expand_env_vars(config)


def _expand_env_vars(value):
    if isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env_vars(v) for v in value]
    if isinstance(value, str):
        return _expand_env_vars_in_str(value)
    return value


_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _expand_env_vars_in_str(value: str) -> str:
    def replacer(match: re.Match) -> str:
        var_name = match.group(1)
        if var_name not in os.environ:
            raise ValueError(f"Missing required environment variable: {var_name}")
        return os.environ[var_name]

    return _ENV_VAR_PATTERN.sub(replacer, value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark runner")
    parser.add_argument("--config", required=True, help="Path to config file")
    args = parser.parse_args()

    config = load_config(args.config)
    pipeline = BenchmarkPipeline(config)
    metric_result = pipeline.run()
    print(json.dumps(metric_result.__dict__, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
