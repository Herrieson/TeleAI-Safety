import os
import json
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# 导入所有可用 scorer，便于通过 --scorer 参数切换
from scorers import *

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scorer', type=str, default='PatternScorer', help='Scorer name')
    parser.add_argument('--config_path', type=str, default='./config/pattern_scorer.yaml', help='Path to config file')
    parser.add_argument('--json_path', type=str, required=True, help='Path to json file for evaluation')
    parser.add_argument('--output_path', type=str, default='eval_summary.txt', help='Path to output summary txt')
    parser.add_argument('--workers', type=int, default=32, help='Number of threads for scoring')
    args = parser.parse_args()

    scorer_name = args.scorer
    json_path = args.json_path
    output_path = args.output_path
    config_path = args.config_path
    workers = max(1, args.workers)

    scorer_class = globals().get(scorer_name, None)
    config_cls = globals().get(f"{scorer_name}Config", None)
    scorer_instance = None
    if scorer_class is not None:
        scorer_instance = scorer_class(config_cls.from_yaml(config_path))
    else:
        raise ValueError(f"Scorer {scorer_name} is not defined or does not have a score method.")
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    base_filename = os.path.basename(output_path)
    base_filename = base_filename.split('.')[0] + f'_{scorer_name}.' + base_filename.split('.')[-1]
    output_path = os.path.join(output_dir, base_filename)

    # Read input json
    with open(json_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    total_samples = 0
    attack_success_count = 0
    skipped_samples = 0
    scorer_asr_sum = 0.0
    scorer_asr_count = 0
    total_lines = len(lines)

    def process_line(line):
        try:
            item = json.loads(line.strip())
        except Exception as e:
            print(f"[Scoring] JSON parse failed: {e}", flush=True)
            return (0, 0, 1, 0.0, 0)
        query = None
        response = None
        query_field_candidates = ['goals', 'query', 'final_query', 'input']
        response_field_candidates = ['response', 'target', 'targets']
        for field in query_field_candidates:
            if field in item:
                query = item[field]
                break
        for field in response_field_candidates:
            if field in item:
                response = item[field]
                break
        if isinstance(response, list) and len(response) == 1:
            response = response[0]
        if not (isinstance(query, str) and isinstance(response, str)):
            return (0, 0, 1, 0.0, 0)
        score = scorer_instance.score(query, response)
        if score is not None and score.get('score') is not None:
            success_flag = int(bool(score['score']))
            # Some scorers may return a numeric ASR/probability; track its average separately.
            scorer_asr_value = score.get('asr', score['score'])
            if isinstance(scorer_asr_value, (int, float)):
                return (1, success_flag, 0, float(scorer_asr_value), 1)
            return (1, success_flag, 0, 0.0, 0)
        return (0, 0, 1, 0.0, 0)

    progress_step = max(1, total_lines // 10) if total_lines else 1
    processed = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(process_line, line) for line in lines]
        for idx, future in enumerate(as_completed(futures), 1):
            total, success, skipped, asr_value, asr_count = future.result()
            total_samples += total
            attack_success_count += success
            skipped_samples += skipped
            scorer_asr_sum += asr_value
            scorer_asr_count += asr_count
            processed += 1
            if total_lines and (processed % progress_step == 0 or processed == total_lines):
                print(f"[Progress] {processed}/{total_lines} processed", flush=True)

    asr = attack_success_count / total_samples if total_samples > 0 else 0.0
    scorer_asr_avg = scorer_asr_sum / scorer_asr_count if scorer_asr_count > 0 else 0.0

    summary_lines = [
        f"Evaluation Summary Report",
        f"Scorer: {scorer_name}",
        f"Input file: {json_path}",
        f"Total samples: {total_samples}",
        f"Skipped samples: {skipped_samples}",
        f"Attack success samples: {attack_success_count}",
        f"Attack Success Rate (ASR): {asr:.4f}",
        f"Average scorer ASR: {scorer_asr_avg:.4f}",
        "",
    ]
    summary_text = "\n".join(summary_lines)

    print(summary_text)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(summary_text + "\n")

if __name__ == "__main__":
    main()
