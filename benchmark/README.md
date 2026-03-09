# Benchmark

Standalone benchmark pipeline for multi-dimension evaluations.

Core flow: dataset -> model -> judge -> metric.

Run:

```bash
python benchmark/cli.py --config benchmark/configs/run.yaml
```

Red-team attack generation (read `final_query`, write model output to `response` in result rows):

```bash
python benchmark/cli.py --config benchmark/configs/run/attack/run_attack_cipher_model_only.yaml
```
