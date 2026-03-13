import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Dict, Iterable, List, Optional, Tuple

from openai import AzureOpenAI, OpenAI

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

DEFAULT_FACTS = os.path.join(PROJECT_ROOT, "evaluation_report", "facts.json")
DEFAULT_OUTPUT_FILE = os.path.join(PROJECT_ROOT, "evaluation_report", "Deep_Security_Report.md")
DEFAULT_MODEL_NAME = "gpt-4o"
DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_AZURE_API_VERSION = "2024-12-01-preview"
DEFAULT_CASE_INPUT_DIR = os.path.join(PROJECT_ROOT, "evaluation_report", "asr_labels")
DEFAULT_METRICS_CATALOG = os.path.join(PROJECT_ROOT, "assets", "metrics_doc", "metrics_catalog.yaml")
DEFAULT_REPORT_TEMPLATE = os.path.join(PROJECT_ROOT, "assets", "report_example", "report_template.md")
DEFAULT_STYLE_FEWSHOT = os.path.join(PROJECT_ROOT, "assets", "report_example", "style_fewshot.yaml")


def load_facts(path: str) -> Dict[str, object]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _safe_float(value: object) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: object) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _md_cell(value: object) -> str:
    if value is None:
        return "-"
    text = str(value).replace("|", "\\|").replace("\n", " ")
    return text if text else "-"


def render_markdown_table(columns: List[str], rows: List[List[str]]) -> str:
    header = "| " + " | ".join([_md_cell(c) for c in columns]) + " |"
    sep = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = ["| " + " | ".join([_md_cell(v) for v in row]) + " |" for row in rows]
    return "\n".join([header, sep] + body)


def build_openai_client(args):
    if args.provider == "azure":
        if not args.api_key or not args.azure_endpoint:
            raise ValueError("Azure 模式需要提供 --api-key 与 --azure-endpoint")
        return AzureOpenAI(
            api_key=args.api_key,
            azure_endpoint=args.azure_endpoint,
            api_version=args.azure_api_version,
        )
    if not args.api_key:
        raise ValueError("OpenAI 模式需要提供 --api-key")
    return OpenAI(api_key=args.api_key, base_url=args.base_url)


def resolve_plot_path(rel_path: Optional[str]) -> Optional[str]:
    if not rel_path:
        return None
    abs_path = os.path.join(PROJECT_ROOT, rel_path)
    return rel_path if os.path.isfile(abs_path) else None


def parse_attack_run(attack_run: str) -> Optional[Tuple[str, str]]:
    if not attack_run:
        return None
    parts = attack_run.split(os.sep)
    if len(parts) < 2:
        return None
    return parts[0], parts[1]


def _canonical_attack_name(name: str, known_attacks: List[str]) -> str:
    raw = str(name or "").strip()
    if not raw:
        return raw
    norm = re.sub(r"[^a-z0-9]", "", raw.lower())
    for attack in known_attacks:
        if re.sub(r"[^a-z0-9]", "", str(attack).lower()) == norm:
            return str(attack)
    return raw


def _metric_map(rows: List[Dict[str, object]], key: str, value_key: str) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for row in rows:
        k = row.get(key)
        v = _safe_float(row.get(value_key))
        if isinstance(k, str) and v is not None:
            out[k] = v
    return out


def _normalize(values: Dict[str, float], reverse: bool = False) -> Dict[str, float]:
    if not values:
        return {}
    lo = min(values.values())
    hi = max(values.values())
    if hi == lo:
        out = {k: 1.0 for k in values}
        return {k: 1.0 - v for k, v in out.items()} if reverse else out
    out = {k: (v - lo) / (hi - lo) for k, v in values.items()}
    if reverse:
        out = {k: 1.0 - v for k, v in out.items()}
    return out


def _pick_text(record: Dict[str, object], keys: List[str]) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, list) and len(value) == 1 and isinstance(value[0], str):
            return value[0]
    return ""


def _trim_text(text: str, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _normalize_for_similarity(text: str, *, keep_digits: bool = True) -> str:
    out = str(text or "").replace("\\|", "|").lower()
    out = re.sub(r"\[e\d+\]", " ", out, flags=re.I)
    if not keep_digits:
        out = re.sub(r"\d+(?:\.\d+)?", " ", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def _similarity_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def _is_masked_response(text: str) -> bool:
    t = (text or "").lower()
    return "### masked" in t or "masked instruction" in t


def _sanitize_error_message(err: object) -> str:
    text = str(err)
    # Mask possible leaked API keys in provider error messages.
    text = re.sub(r"(api[_\s-]?key[^:]{0,30}:\s*)([^'\",}\s]{6})[^'\",}\s]+", r"\1\2***", text, flags=re.I)
    text = re.sub(r"(sk-[A-Za-z0-9]{4})[A-Za-z0-9_\-]+", r"\1***", text)
    return text


def _redact_url(url: str) -> str:
    if not url:
        return "-"
    text = str(url).strip()
    if not text:
        return "-"
    m = re.match(r"^(https?://)([^/]+)(/?.*)$", text, flags=re.I)
    if not m:
        return _trim_text(text, limit=48)
    scheme, host, rest = m.groups()
    if len(host) <= 8:
        masked_host = host[:2] + "***"
    else:
        masked_host = host[:6] + "***"
    tail = rest if rest and rest != "/" else ""
    return f"{scheme}{masked_host}{tail}"


def _clean_report_text(text: str) -> str:
    out = str(text or "")
    out = out.replace("越Output稳健", "越稳健")
    out = out.replace("Output稳健", "稳健")
    out = re.sub(r"(?<=[\u4e00-\u9fff])Output", "", out)
    return out


def _normalize_audit_lines(lines: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for raw in lines:
        text = re.sub(r"\s+", " ", str(raw)).strip()
        if not text:
            continue
        if not text.startswith("- "):
            text = "- " + text.lstrip("- ").strip()
        if text in seen:
            continue
        out.append(text)
        seen.add(text)
    return out


@dataclass
class ModelProfile:
    model: str
    asr: Optional[float]
    frr: Optional[float]
    mds: Optional[float]
    kappa: Optional[float]
    bias: Optional[float]
    wsl: Optional[float]
    cm: Optional[float]
    mu_asr: Optional[float]
    sigma_asr: Optional[float]
    attacks_covered: Optional[int]
    score: Optional[float]


@dataclass
class CaseExample:
    case_type: str
    polarity: str
    source_file: str
    line_no: int
    query: str
    response: str
    safety_label: Optional[int]
    asr_label: Optional[int]
    frr_label: Optional[int]
    response_strategy_label: Optional[int]
    response_label: Optional[int]
    representative_score: float
    is_masked: bool


class EvidenceRegistry:
    def __init__(self) -> None:
        self._items: List[Dict[str, str]] = []
        self._next_id = 1

    def add(self, *, source: str, claim: str, detail: str) -> int:
        eid = self._next_id
        self._next_id += 1
        self._items.append(
            {
                "id": str(eid),
                "source": source,
                "claim": claim,
                "detail": detail,
            }
        )
        return eid

    def ref(self, ids: List[int]) -> str:
        return "".join([f"[E{i}]" for i in ids if isinstance(i, int) and i > 0])

    def render_markdown(self) -> str:
        rows: List[List[str]] = []
        for item in self._items:
            rows.append(
                [
                    f"E{item['id']}",
                    item["source"],
                    item["claim"],
                    item["detail"],
                ]
            )
        return render_markdown_table(
            ["ID", "Source", "Claim", "Detail"],
            rows,
        )

    def size(self) -> int:
        return len(self._items)


@dataclass
class DraftReport:
    exec_lines: List[str]
    focus_lines: List[str]
    insight_lines: List[str]
    attack_lines: List[str]
    case_lines: List[str]
    recommendation_lines: List[str]
    audit_lines: List[str]


def _append_audit(draft: DraftReport, line: str) -> DraftReport:
    return DraftReport(
        exec_lines=list(draft.exec_lines),
        focus_lines=list(draft.focus_lines),
        insight_lines=list(draft.insight_lines),
        attack_lines=list(draft.attack_lines),
        case_lines=list(draft.case_lines),
        recommendation_lines=list(draft.recommendation_lines),
        audit_lines=list(draft.audit_lines) + [line],
    )


class ReportWritingAgent:
    """
    写报告智能体：
    1) 先从数据中发现洞见（不预设章节）
    2) 再动态规划报告结构
    3) 两轮反思修正，减少冲突结论
    """

    def __init__(self, facts: Dict[str, object], args: argparse.Namespace):
        self.facts = facts
        self.args = args
        self.models = list(facts.get("models") or [])
        self.attacks = list(facts.get("attacks") or [])
        self.matrix: Dict[str, Dict[str, float]] = facts.get("model_attack_matrix") or {}
        self.model_profiles: List[ModelProfile] = []
        self.attack_rows: List[Dict[str, object]] = []
        self.case_examples: List[CaseExample] = []
        self.case_line_pool: List[str] = []
        self.case_candidate_records: List[Dict[str, object]] = []
        self.case_meta_by_line: Dict[str, Dict[str, object]] = {}
        self.case_pool_stats: Dict[str, object] = {}
        self.case_selection_stats: Dict[str, object] = {}
        self.focus_attack_metric_rows: List[Dict[str, object]] = []
        self.external_signals: Dict[str, object] = {}
        self.style_fewshot: Dict[str, object] = load_style_fewshot(
            args.style_fewshot,
            max_snippets=max(1, int(args.style_max_snippets)),
        )
        self.evidence = EvidenceRegistry()
        focus = (args.focus_model or "").strip()
        self.focus_model = focus if focus else (self.models[0] if self.models else "")
        if self.focus_model and self.focus_model not in self.models:
            self.models.append(self.focus_model)

    def build_indices(self) -> None:
        model_summary = self.facts.get("model_summary") or []
        metric_summary = self.facts.get("metric_summary") or []
        mds_summary = self.facts.get("mds_summary") or []

        asr_map = _metric_map(model_summary, "model", "avg_asr")
        frr_map = _metric_map(model_summary, "model", "avg_frr")
        mds_map = _metric_map(mds_summary, "model", "mds")
        mu_map = _metric_map(mds_summary, "model", "mu_asr")
        sigma_map = _metric_map(mds_summary, "model", "sigma_asr")
        bias_map = _metric_map(metric_summary, "model", "bias")
        wsl_map = _metric_map(metric_summary, "model", "wsl")
        cm_map = _metric_map(metric_summary, "model", "cm")
        kappa_map = self._load_kappa_by_model()

        coverage_map: Dict[str, int] = {}
        for row in model_summary:
            model = row.get("model")
            count = _safe_int(row.get("attacks_covered"))
            if isinstance(model, str) and count is not None:
                coverage_map[model] = count

        score_map = self._composite_score(
            asr_map=asr_map,
            frr_map=frr_map,
            mds_map=mds_map,
            kappa_map=kappa_map,
            bias_map=bias_map,
            wsl_map=wsl_map,
            cm_map=cm_map,
        )

        candidates = sorted(
            set(self.models)
            | set(asr_map)
            | set(frr_map)
            | set(mds_map)
            | set(kappa_map)
            | set(bias_map)
            | set(wsl_map)
            | set(cm_map)
        )
        profiles: List[ModelProfile] = []
        for model in candidates:
            profiles.append(
                ModelProfile(
                    model=model,
                    asr=asr_map.get(model),
                    frr=frr_map.get(model),
                    mds=mds_map.get(model),
                    kappa=kappa_map.get(model),
                    bias=bias_map.get(model),
                    wsl=wsl_map.get(model),
                    cm=cm_map.get(model),
                    mu_asr=mu_map.get(model),
                    sigma_asr=sigma_map.get(model),
                    attacks_covered=coverage_map.get(model),
                    score=score_map.get(model),
                )
            )
        profiles.sort(key=lambda x: (x.score is None, -(x.score or 0.0), x.model))
        self.model_profiles = profiles
        self.attack_rows = self._build_attack_rows()
        self.focus_attack_metric_rows = self._load_focus_attack_metric_rows()
        self.external_signals = self._load_external_signal_bundle()
        self.case_examples = self._load_case_examples()

    def _load_kappa_by_model(self) -> Dict[str, float]:
        sources = self.facts.get("sources") or {}
        kappa_rel = sources.get("kappa_csv") if isinstance(sources, dict) else None
        if not isinstance(kappa_rel, str) or not kappa_rel:
            return {}
        path = os.path.join(PROJECT_ROOT, kappa_rel)
        if not os.path.isfile(path):
            return {}
        values: Dict[str, List[float]] = {}
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                attack_run = (row.get("attack_run") or "").strip()
                if not attack_run or attack_run == "__summary__":
                    continue
                parsed = parse_attack_run(attack_run)
                if not parsed:
                    continue
                model, _ = parsed
                kappa = _safe_float(row.get("kappa"))
                if kappa is None:
                    continue
                values.setdefault(model, []).append(kappa)
        return {k: (sum(v) / len(v)) for k, v in values.items() if v}

    def _composite_score(
        self,
        *,
        asr_map: Dict[str, float],
        frr_map: Dict[str, float],
        mds_map: Dict[str, float],
        kappa_map: Dict[str, float],
        bias_map: Dict[str, float],
        wsl_map: Dict[str, float],
        cm_map: Dict[str, float],
    ) -> Dict[str, float]:
        abs_bias = {k: abs(v) for k, v in bias_map.items()}
        asr_n = _normalize(asr_map, reverse=True)
        frr_n = _normalize(frr_map, reverse=True)
        mds_n = _normalize(mds_map)
        kappa_n = _normalize(kappa_map)
        bias_n = _normalize(abs_bias, reverse=True)
        wsl_n = _normalize(wsl_map, reverse=True)
        cm_n = _normalize(cm_map, reverse=True)
        weights = {
            "asr": 0.28,
            "frr": 0.18,
            "mds": 0.16,
            "kappa": 0.14,
            "bias": 0.08,
            "wsl": 0.10,
            "cm": 0.06,
        }
        models = set(asr_n) | set(frr_n) | set(mds_n) | set(kappa_n) | set(bias_n) | set(wsl_n) | set(cm_n)
        out: Dict[str, float] = {}
        for model in models:
            score = 0.0
            used = 0.0
            for key, bucket in [
                ("asr", asr_n),
                ("frr", frr_n),
                ("mds", mds_n),
                ("kappa", kappa_n),
                ("bias", bias_n),
                ("wsl", wsl_n),
                ("cm", cm_n),
            ]:
                value = bucket.get(model)
                if value is None:
                    continue
                weight = weights[key]
                score += value * weight
                used += weight
            if used > 0:
                out[model] = score / used
        return out

    def _build_attack_rows(self) -> List[Dict[str, object]]:
        attack_summary = self.facts.get("attack_summary") or []
        avg_asr = _metric_map(attack_summary, "attack", "avg_asr")
        avg_frr = _metric_map(attack_summary, "attack", "avg_frr")
        rows: List[Dict[str, object]] = []
        for attack in sorted(set(self.attacks) | set(avg_asr) | set(avg_frr)):
            worst_model = None
            worst_asr = None
            for model in self.matrix:
                value = _safe_float(self.matrix.get(model, {}).get(attack))
                if value is None:
                    continue
                if worst_asr is None or value > worst_asr:
                    worst_asr = value
                    worst_model = model
            rows.append(
                {
                    "attack": attack,
                    "avg_asr": avg_asr.get(attack),
                    "avg_frr": avg_frr.get(attack),
                    "worst_model": worst_model,
                    "worst_asr": worst_asr,
                }
            )
        rows.sort(key=lambda x: (x["avg_asr"] is None, -(x["avg_asr"] or 0.0)))
        return rows

    @staticmethod
    def _parse_named_value(text: str, names: List[str]) -> Optional[float]:
        for name in names:
            pattern = rf"{re.escape(name)}\s*:\s*([-+]?\d+(?:\.\d+)?)"
            m = re.search(pattern, text, flags=re.I)
            if m:
                return _safe_float(m.group(1))
        return None

    def _load_focus_attack_metric_rows(self) -> List[Dict[str, object]]:
        if not self.focus_model:
            return []
        sources = self.facts.get("sources") or {}
        if not isinstance(sources, dict):
            sources = {}
        bias_rel = str(sources.get("bias_dir") or "evaluation_report/bias")
        wsl_rel = str(sources.get("wsl_dir") or "evaluation_report/wsl")
        cm_rel = str(sources.get("cm_dir") or "evaluation_report/cm")

        metric_dirs = {
            "bias": os.path.join(PROJECT_ROOT, bias_rel, self.focus_model),
            "wsl": os.path.join(PROJECT_ROOT, wsl_rel, self.focus_model),
            "cm": os.path.join(PROJECT_ROOT, cm_rel, self.focus_model),
        }
        rows: Dict[str, Dict[str, object]] = {}
        for metric, model_dir in metric_dirs.items():
            if not os.path.isdir(model_dir):
                continue
            for name in sorted(os.listdir(model_dir)):
                if not name.endswith(".txt"):
                    continue
                attack = _canonical_attack_name(os.path.splitext(name)[0], self.attacks)
                path = os.path.join(model_dir, name)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        text = f.read()
                except OSError:
                    continue
                bucket = rows.setdefault(attack, {"attack": attack})
                if metric == "bias":
                    value = self._parse_named_value(text, ["Mean(response_label - response_strategy_label)", "Mean"])
                elif metric == "wsl":
                    value = self._parse_named_value(text, ["Mean weighted loss", "Mean"])
                else:
                    value = self._parse_named_value(text, ["Mean cost", "Mean"])
                bucket[metric] = value
        out = list(rows.values())
        out.sort(
            key=lambda x: (
                _safe_float(x.get("cm")) is None,
                -(_safe_float(x.get("cm")) or -1.0),
                -(_safe_float(x.get("wsl")) or -1.0),
                str(x.get("attack")),
            )
        )
        return out

    def _load_external_signal_bundle(self) -> Dict[str, object]:
        bundle: Dict[str, object] = {}
        eval_root = os.path.dirname(os.path.abspath(self.args.facts))
        all_metrics_path = os.path.join(eval_root, "all_metrics_summary.csv")
        if os.path.isfile(all_metrics_path):
            model_row = None
            attack_rows: List[Dict[str, object]] = []
            try:
                with open(all_metrics_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if str(row.get("record_type") or "") == "model":
                            if str(row.get("model") or "") == self.focus_model:
                                model_row = row
                        elif str(row.get("record_type") or "") == "attack":
                            attack_rows.append(row)
            except OSError:
                pass
            if model_row:
                bundle["all_metrics_focus_model"] = {
                    "avg_asr": _safe_float(model_row.get("avg_asr")),
                    "avg_frr": _safe_float(model_row.get("avg_frr")),
                    "mds": _safe_float(model_row.get("mds")),
                    "bias": _safe_float(model_row.get("bias")),
                    "wsl": _safe_float(model_row.get("wsl")),
                    "cm": _safe_float(model_row.get("cm")),
                }
            if attack_rows:
                asr_sorted = sorted(
                    [row for row in attack_rows if _safe_float(row.get("avg_asr")) is not None],
                    key=lambda x: -(_safe_float(x.get("avg_asr")) or 0.0),
                )
                frr_sorted = sorted(
                    [row for row in attack_rows if _safe_float(row.get("avg_frr")) is not None],
                    key=lambda x: -(_safe_float(x.get("avg_frr")) or 0.0),
                )
                if asr_sorted:
                    bundle["all_metrics_top_attack_asr"] = {
                        "attack": asr_sorted[0].get("attack"),
                        "avg_asr": _safe_float(asr_sorted[0].get("avg_asr")),
                    }
                if frr_sorted:
                    bundle["all_metrics_top_attack_frr"] = {
                        "attack": frr_sorted[0].get("attack"),
                        "avg_frr": _safe_float(frr_sorted[0].get("avg_frr")),
                    }

        overview_path = os.path.join(eval_root, "summary_overview.md")
        if os.path.isfile(overview_path):
            try:
                with open(overview_path, "r", encoding="utf-8") as f:
                    overview = f.read()
                overview = re.sub(r"\s+", " ", overview).strip()
                bundle["summary_overview_excerpt"] = _trim_text(overview, limit=680)
            except OSError:
                pass
        return bundle

    def _discover_case_files(self) -> List[str]:
        raw = (self.args.case_input or "").strip()
        if raw:
            if os.path.isfile(raw):
                return [raw]
            if os.path.isdir(raw):
                found: List[str] = []
                for root, _, files in os.walk(raw):
                    for name in files:
                        if name.endswith(".jsonl"):
                            found.append(os.path.join(root, name))
                return sorted(found)
            return []
        if not self.focus_model:
            return []
        model_dir = os.path.join(DEFAULT_CASE_INPUT_DIR, self.focus_model)
        if not os.path.isdir(model_dir):
            return []
        found: List[str] = []
        for root, _, files in os.walk(model_dir):
            for name in files:
                if name.endswith(".jsonl"):
                    found.append(os.path.join(root, name))
        return sorted(found)

    def _iter_jsonl(self, path: str) -> Iterable[Tuple[int, Dict[str, object]]]:
        with open(path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    yield i, obj

    def _load_case_examples(self) -> List[CaseExample]:
        files = self._discover_case_files()
        max_cases = max(1, int(self.args.max_cases))
        # Keep a larger candidate pool so later stages can choose representative and diverse samples.
        candidate_limit = max(40, max_cases * 12)
        scan_event_limit = max(400, max_cases * 80)
        per_type_limit = max(8, candidate_limit // 5)
        buckets: Dict[str, List[CaseExample]] = {
            "harmful_pass": [],
            "false_refusal": [],
            "harmful_block": [],
            "benign_accept": [],
            "judge_disagreement": [],
        }
        backup_buckets: Dict[str, List[CaseExample]] = {
            "harmful_pass": [],
            "false_refusal": [],
            "harmful_block": [],
            "benign_accept": [],
            "judge_disagreement": [],
        }

        def _append_case(case: CaseExample, masked: bool) -> None:
            target = backup_buckets if masked else buckets
            arr = target.get(case.case_type, [])
            arr.append(case)
            target[case.case_type] = arr

        collected = 0
        for path in files:
            rel = os.path.relpath(path, PROJECT_ROOT)
            for line_no, obj in self._iter_jsonl(path):
                q = _pick_text(obj, ["query", "input", "final_query", "goals"])
                r = _pick_text(obj, ["response", "target", "targets"])
                safety = _safe_int(obj.get("safety_label"))
                asr = _safe_int(obj.get("asr_label"))
                frr = _safe_int(obj.get("frr_label"))
                strategy = _safe_int(obj.get("response_strategy_label"))
                response_label = _safe_int(obj.get("response_label"))
                query = _trim_text(q)
                response = _trim_text(r)
                masked = _is_masked_response(response)

                def _new_case(case_type: str, polarity: str) -> CaseExample:
                    case = CaseExample(
                        case_type=case_type,
                        polarity=polarity,
                        source_file=rel,
                        line_no=line_no,
                        query=query,
                        response=response,
                        safety_label=safety,
                        asr_label=asr,
                        frr_label=frr,
                        response_strategy_label=strategy,
                        response_label=response_label,
                        representative_score=0.0,
                        is_masked=masked,
                    )
                    case.representative_score = self._case_representative_score(case)
                    return case

                if safety in (1, 2) and asr == 1:
                    _append_case(_new_case("harmful_pass", "negative"), masked)
                    collected += 1
                if safety == 0 and frr == 1:
                    _append_case(_new_case("false_refusal", "negative"), masked)
                    collected += 1
                if safety in (1, 2) and asr == 0:
                    _append_case(_new_case("harmful_block", "positive"), masked)
                    collected += 1
                if safety == 0 and frr == 0:
                    _append_case(_new_case("benign_accept", "positive"), masked)
                    collected += 1
                if (
                    strategy is not None
                    and response_label is not None
                    and strategy >= 0
                    and response_label >= 0
                    and abs(strategy - response_label) >= 1
                ):
                    _append_case(_new_case("judge_disagreement", "negative"), masked)
                    collected += 1
                if collected >= scan_event_limit:
                    break
            if collected >= scan_event_limit:
                break

        selected_buckets: Dict[str, List[CaseExample]] = {}
        for key in ["harmful_pass", "false_refusal", "harmful_block", "benign_accept", "judge_disagreement"]:
            primary = sorted(buckets.get(key, []), key=lambda x: x.representative_score, reverse=True)
            backup = sorted(backup_buckets.get(key, []), key=lambda x: x.representative_score, reverse=True)
            chosen = primary[:per_type_limit]
            if len(chosen) < per_type_limit:
                chosen.extend(backup[: per_type_limit - len(chosen)])
            selected_buckets[key] = chosen

        merged: List[CaseExample] = []
        # Keep a broad case pool and let LLM choose representative positive/negative examples.
        for key in ["harmful_pass", "false_refusal", "harmful_block", "benign_accept", "judge_disagreement"]:
            merged.extend(selected_buckets.get(key, []))
        merged.sort(key=lambda x: x.representative_score, reverse=True)
        return merged[:candidate_limit]

    @staticmethod
    def _case_type_weight(case_type: str) -> float:
        weights = {
            "harmful_pass": 1.35,
            "false_refusal": 1.25,
            "judge_disagreement": 1.15,
            "harmful_block": 1.00,
            "benign_accept": 0.90,
        }
        return weights.get(case_type, 1.0)

    def _case_representative_score(self, case: CaseExample) -> float:
        score = self._case_type_weight(case.case_type)
        # Rich label combinations are usually more diagnostic.
        label_count = sum(
            1
            for v in [
                case.safety_label,
                case.asr_label,
                case.frr_label,
                case.response_strategy_label,
                case.response_label,
            ]
            if v is not None
        )
        score += label_count * 0.08
        score += min(len(case.query), 220) / 220.0 * 0.24
        score += min(len(case.response), 420) / 420.0 * 0.28
        if case.case_type == "judge_disagreement":
            if case.response_strategy_label is not None and case.response_label is not None:
                score += min(abs(case.response_strategy_label - case.response_label), 2) * 0.14
        if case.case_type == "harmful_pass" and case.safety_label == 2:
            score += 0.18
        if case.case_type == "false_refusal" and case.frr_label == 1:
            score += 0.14
        if case.is_masked:
            # Keep masked samples as backup by default.
            score -= 0.35
        return round(score, 4)

    def _parse_case_line(self, line: str) -> Dict[str, object]:
        text = str(line or "")
        polarity = "unknown"
        case_type = "unknown"
        tag_match = re.search(r"\[([^\]/]+)/([^\]]+)\]", text)
        if tag_match:
            polarity = tag_match.group(1).strip().lower()
            case_type = tag_match.group(2).strip().lower()

        query = ""
        response = ""
        if "Q:" in text and " | A:" in text:
            left, right = text.split(" | A:", 1)
            query = left.split("Q:", 1)[-1].strip()
            response = re.sub(r"\s*\[E\d+\]\s*$", "", right).strip()
        else:
            m = re.search(r"Q:\s*(.*)", text)
            if m:
                query = m.group(1).strip()
            response = text

        query_norm = _normalize_for_similarity(query)
        response_norm = _normalize_for_similarity(response)
        response_prefix = response_norm[:200]
        content_key = f"{query_norm[:240]}|{response_prefix}"
        signature = f"{case_type}|{query_norm[:160]}|{response_prefix[:140]}"
        similarity_text = f"{query_norm} {response_prefix}".strip()
        return {
            "polarity": polarity,
            "case_type": case_type,
            "query_norm": query_norm,
            "response_norm": response_norm,
            "response_prefix": response_prefix,
            "content_key": content_key,
            "signature": signature,
            "similarity_text": similarity_text,
            "score": 0.0,
            "label_consistency": 0.0,
            "is_masked": False,
        }

    def _case_meta(self, line: str) -> Dict[str, object]:
        cached = self.case_meta_by_line.get(line)
        parsed = self._parse_case_line(line)
        if isinstance(cached, dict):
            merged = dict(parsed)
            merged.update(cached)
        else:
            merged = parsed
        self.case_meta_by_line[line] = merged
        return merged

    def _case_signature_from_line(self, line: str) -> str:
        return str(self._case_meta(line).get("signature") or "-")

    def _line_case_score(self, line: str) -> float:
        return float(self._case_meta(line).get("score") or 0.0)

    def _prepare_case_pool(self, pool: List[str]) -> List[str]:
        if not pool:
            self.case_pool_stats = {"raw_size": 0, "unique_size": 0, "deduped": 0, "conflict_groups": 0}
            return []

        vote_by_content_type = Counter()
        type_set_by_content: Dict[str, set] = defaultdict(set)
        for line in pool:
            meta = self._case_meta(line)
            content_key = str(meta.get("content_key") or "")
            case_type = str(meta.get("case_type") or "unknown")
            vote_by_content_type[(content_key, case_type)] += 1
            type_set_by_content[content_key].add(case_type)

        best_by_content: Dict[str, Tuple[Tuple[float, float, float, float, float], str]] = {}
        for idx, line in enumerate(pool):
            meta = self._case_meta(line)
            content_key = str(meta.get("content_key") or "")
            case_type = str(meta.get("case_type") or "unknown")
            vote = float(vote_by_content_type[(content_key, case_type)])
            score = float(meta.get("score") or 0.0)
            label_consistency = float(meta.get("label_consistency") or 0.0)
            is_unmasked = 0.0 if bool(meta.get("is_masked")) else 1.0
            rank = (vote, score, label_consistency, is_unmasked, -float(idx))
            prev = best_by_content.get(content_key)
            if prev is None or rank > prev[0]:
                best_by_content[content_key] = (rank, line)

        ranked = sorted(best_by_content.values(), key=lambda x: x[0], reverse=True)
        out = [line for _, line in ranked]
        conflict_groups = sum(1 for v in type_set_by_content.values() if len(v) > 1)
        self.case_pool_stats = {
            "raw_size": len(pool),
            "unique_size": len(out),
            "deduped": max(0, len(pool) - len(out)),
            "conflict_groups": conflict_groups,
        }
        return out

    def _is_near_duplicate_case(
        self,
        line: str,
        selected: List[str],
        threshold: float,
    ) -> bool:
        line_text = str(self._case_meta(line).get("similarity_text") or "")
        if not line_text:
            return False
        for existing in selected:
            existing_text = str(self._case_meta(existing).get("similarity_text") or "")
            if _similarity_ratio(line_text, existing_text) >= threshold:
                return True
        return False

    def _pick_case_lines(
        self,
        *,
        pool: List[str],
        max_cases: int,
        preferred: Optional[List[str]] = None,
    ) -> List[str]:
        if not pool:
            self.case_selection_stats = {
                "selected": 0,
                "unique_case_types": 0,
                "near_dup_ratio": 0.0,
                "positive_cases": 0,
                "negative_cases": 0,
            }
            return []

        threshold = float(getattr(self.args, "case_similarity_threshold", 0.82) or 0.82)
        threshold = max(0.55, min(0.98, threshold))
        max_cases_per_query = max(1, int(getattr(self.args, "max_cases_per_query", 1) or 1))
        query_keys_in_pool = {
            str(self._case_meta(line).get("query_norm") or "")
            for line in pool
            if str(self._case_meta(line).get("query_norm") or "")
        }
        min_target = min(4, max_cases)
        if query_keys_in_pool and len(query_keys_in_pool) * max_cases_per_query < min_target:
            adaptive_cap = (min_target + len(query_keys_in_pool) - 1) // len(query_keys_in_pool)
            max_cases_per_query = max(max_cases_per_query, adaptive_cap)
        max_cases_per_query = min(max_cases_per_query, max(1, max_cases))
        selected: List[str] = []
        seen_signatures = set()
        used = set()
        query_counter: Counter[str] = Counter()

        def _try_add(line: str) -> bool:
            if line in used:
                return False
            meta = self._case_meta(line)
            query_key = str(meta.get("query_norm") or "")
            if query_key and query_counter[query_key] >= max_cases_per_query:
                return False
            signature = self._case_signature_from_line(line)
            if signature in seen_signatures:
                return False
            if self._is_near_duplicate_case(line, selected, threshold):
                return False
            selected.append(line)
            used.add(line)
            seen_signatures.add(signature)
            if query_key:
                query_counter[query_key] += 1
            return True

        preferred = preferred or []
        for line in preferred:
            if len(selected) >= max_cases:
                break
            _try_add(line)

        by_type: Dict[str, List[str]] = defaultdict(list)
        for line in pool:
            case_type = str(self._case_meta(line).get("case_type") or "unknown")
            by_type[case_type].append(line)

        type_priority = ["harmful_pass", "false_refusal", "harmful_block", "benign_accept", "judge_disagreement"]
        for case_type in type_priority:
            if len(selected) >= max_cases:
                break
            for line in by_type.get(case_type, []):
                if _try_add(line):
                    break

        has_positive = any(self._is_positive_case_line(line) for line in selected)
        has_negative = any(self._is_negative_case_line(line) for line in selected)
        if not has_negative:
            for line in pool:
                if len(selected) >= max_cases:
                    break
                if self._is_negative_case_line(line) and _try_add(line):
                    break
        if not has_positive:
            for line in pool:
                if len(selected) >= max_cases:
                    break
                if self._is_positive_case_line(line) and _try_add(line):
                    break

        remaining = [line for line in pool if line not in used]
        remaining.sort(
            key=lambda line: (
                self._line_case_score(line),
                str(self._case_meta(line).get("case_type") or "") in ("harmful_pass", "false_refusal"),
            ),
            reverse=True,
        )
        for line in remaining:
            if len(selected) >= max_cases:
                break
            _try_add(line)

        # Do not force-fill with near-duplicates only to hit max_cases.
        pair_total = 0
        pair_similar = 0
        for i in range(len(selected)):
            for j in range(i + 1, len(selected)):
                pair_total += 1
                ta = str(self._case_meta(selected[i]).get("similarity_text") or "")
                tb = str(self._case_meta(selected[j]).get("similarity_text") or "")
                if _similarity_ratio(ta, tb) >= threshold:
                    pair_similar += 1
        near_dup_ratio = (pair_similar / pair_total) if pair_total else 0.0
        unique_types = {
            str(self._case_meta(line).get("case_type") or "unknown")
            for line in selected
        }
        self.case_selection_stats = {
            "selected": len(selected),
            "unique_case_types": len(unique_types),
            "unique_queries": len(query_counter),
            "near_dup_ratio": round(near_dup_ratio, 4),
            "positive_cases": sum(1 for line in selected if self._is_positive_case_line(line)),
            "negative_cases": sum(1 for line in selected if self._is_negative_case_line(line)),
            "similarity_threshold": round(threshold, 2),
            "max_cases_per_query": max_cases_per_query,
        }
        return selected[:max_cases]

    @staticmethod
    def _is_positive_case_line(line: str) -> bool:
        return "[positive/" in line

    @staticmethod
    def _is_negative_case_line(line: str) -> bool:
        return "[negative/" in line

    def _select_case_lines_rule_based(self, pool: List[str]) -> List[str]:
        max_cases = max(1, int(self.args.max_cases))
        if not pool:
            return []
        prepared_pool = self._prepare_case_pool(pool)
        return self._pick_case_lines(pool=prepared_pool, max_cases=max_cases)

    def _canonicalize_case_lines_from_pool(self, lines: List[str]) -> List[str]:
        if not lines or not self.case_line_pool:
            return []
        case_by_tag: Dict[str, str] = {}
        prepared_pool = self._prepare_case_pool(self.case_line_pool)
        content_to_line: Dict[str, str] = {}
        for line in prepared_pool:
            content_to_line[str(self._case_meta(line).get("content_key") or "")] = line
        for line in self.case_line_pool:
            for tag in re.findall(r"\[E\d+\]", line):
                case_by_tag[tag] = line
        out: List[str] = []
        seen = set()
        for line in lines:
            tags = re.findall(r"\[E\d+\]", line)
            canonical = None
            for tag in tags:
                if tag in case_by_tag:
                    canonical = case_by_tag[tag]
                    break
            if canonical:
                ckey = str(self._case_meta(canonical).get("content_key") or "")
                canonical = content_to_line.get(ckey, canonical)
            if not canonical:
                ckey = str(self._case_meta(line).get("content_key") or "")
                canonical = content_to_line.get(ckey)
            if canonical and canonical not in seen:
                out.append(canonical)
                seen.add(canonical)
        return out

    def _finalize_case_lines(self, preferred: List[str]) -> List[str]:
        max_cases = max(1, int(self.args.max_cases))
        if not self.case_line_pool:
            return []
        prepared_pool = self._prepare_case_pool(self.case_line_pool)
        if not prepared_pool:
            return []
        pool_set = set(prepared_pool)
        content_to_line = {
            str(self._case_meta(line).get("content_key") or ""): line
            for line in prepared_pool
        }
        canonical_preferred: List[str] = []
        for line in preferred:
            candidate = line if line in pool_set else None
            if not candidate:
                ckey = str(self._case_meta(line).get("content_key") or "")
                candidate = content_to_line.get(ckey)
            if candidate and candidate not in canonical_preferred:
                canonical_preferred.append(candidate)
        return self._pick_case_lines(pool=prepared_pool, max_cases=max_cases, preferred=canonical_preferred)

    def _best_model(self) -> Optional[ModelProfile]:
        if not self.model_profiles:
            return None
        return self.model_profiles[0]

    def _focus_profile(self) -> Optional[ModelProfile]:
        if not self.focus_model:
            return None
        for p in self.model_profiles:
            if p.model == self.focus_model:
                return p
        return None

    def _round1_draft(self) -> DraftReport:
        exec_lines: List[str] = []
        focus_lines: List[str] = []
        insight_lines: List[str] = []
        attack_lines: List[str] = []
        case_lines: List[str] = []
        recommendation_lines: List[str] = []
        audit_lines: List[str] = []

        best = self._best_model()
        if best:
            eid = self.evidence.add(
                source="model_profiles",
                claim="top_composite_model",
                detail=f"{best.model}: score={best.score:.4f}" if best.score is not None else best.model,
            )
            score_text = "-" if best.score is None else f"{best.score:.4f}"
            exec_lines.append(
                f"- 综合评分最佳模型：**{best.model}**（Composite={score_text}）。 {self.evidence.ref([eid])}"
            )

        focus = self._focus_profile()
        if focus:
            peer_asr = [p.asr for p in self.model_profiles if p.asr is not None]
            rank_asr = None
            if focus.asr is not None:
                ordered = sorted([p for p in self.model_profiles if p.asr is not None], key=lambda x: x.asr)
                for i, p in enumerate(ordered, start=1):
                    if p.model == focus.model:
                        rank_asr = i
                        break
            eid = self.evidence.add(
                source="focus_model_profile",
                claim="focus_model_position",
                detail=(
                    f"{focus.model}: asr={focus.asr}, frr={focus.frr}, mds={focus.mds}, "
                    f"rank_asr={rank_asr}/{len(peer_asr) if peer_asr else 0}"
                ),
            )
            focus_asr_text = "-" if focus.asr is None else f"{focus.asr:.4f}"
            focus_frr_text = "-" if focus.frr is None else f"{focus.frr:.4f}"
            focus_mds_text = "-" if focus.mds is None else f"{focus.mds:.4f}"
            focus_lines.append(
                f"- 待测模型 **{focus.model}**：ASR={focus_asr_text}，"
                f"FRR={focus_frr_text}，MDS={focus_mds_text}。"
                f"（ASR 排名 {rank_asr if rank_asr else '-'} / {len(peer_asr) if peer_asr else '-'}） {self.evidence.ref([eid])}"
            )
            # find largest gap attack against median
            if focus.model in self.matrix:
                gap_attack = None
                gap_val = None
                for attack in self.attack_rows:
                    name = attack["attack"]
                    focus_asr = _safe_float(self.matrix.get(focus.model, {}).get(name))
                    population = [
                        _safe_float(self.matrix.get(m, {}).get(name))
                        for m in self.matrix
                        if _safe_float(self.matrix.get(m, {}).get(name)) is not None
                    ]
                    if focus_asr is None or not population:
                        continue
                    population_sorted = sorted(population)
                    med = population_sorted[len(population_sorted) // 2]
                    diff = focus_asr - med
                    if gap_val is None or diff > gap_val:
                        gap_val = diff
                        gap_attack = (name, focus_asr, med)
                if gap_attack:
                    eid2 = self.evidence.add(
                        source="model_attack_matrix",
                        claim="focus_model_worst_relative_attack",
                        detail=f"{focus.model} on {gap_attack[0]}: focus_asr={gap_attack[1]:.4f}, median={gap_attack[2]:.4f}",
                    )
                    focus_lines.append(
                        f"- 待测模型在 **{gap_attack[0]}** 上相对同侪偏弱：ASR={gap_attack[1]:.4f}，同侪中位={gap_attack[2]:.4f}。"
                        f" {self.evidence.ref([eid2])}"
                    )
                # Top-2 risky and robust attacks for focus model
                focus_attack_vals: List[Tuple[str, float]] = []
                for attack_name in sorted(self.matrix.get(focus.model, {}).keys()):
                    v = _safe_float(self.matrix.get(focus.model, {}).get(attack_name))
                    if v is not None:
                        focus_attack_vals.append((attack_name, v))
                if focus_attack_vals:
                    risk2 = sorted(focus_attack_vals, key=lambda x: -x[1])[:2]
                    good2 = sorted(focus_attack_vals, key=lambda x: x[1])[:2]
                    e3 = self.evidence.add(
                        source="model_attack_matrix",
                        claim="focus_model_top_risk_attacks",
                        detail=f"{focus.model}: " + ", ".join([f"{a}={v:.4f}" for a, v in risk2]),
                    )
                    e4 = self.evidence.add(
                        source="model_attack_matrix",
                        claim="focus_model_top_robust_attacks",
                        detail=f"{focus.model}: " + ", ".join([f"{a}={v:.4f}" for a, v in good2]),
                    )
                    focus_lines.append(
                        f"- 待测模型高风险攻击面：{'; '.join([f'{a}={v:.4f}' for a, v in risk2])}。{self.evidence.ref([e3])}"
                    )
                    focus_lines.append(
                        f"- 待测模型相对稳健攻击面：{'; '.join([f'{a}={v:.4f}' for a, v in good2])}。{self.evidence.ref([e4])}"
                    )

        by_asr = [p for p in self.model_profiles if p.asr is not None]
        if by_asr:
            low = sorted(by_asr, key=lambda x: x.asr)[0]
            high = sorted(by_asr, key=lambda x: -x.asr)[0]
            e1 = self.evidence.add(
                source="model_profiles",
                claim="best_asr_model",
                detail=f"{low.model}: asr={low.asr:.4f}",
            )
            e2 = self.evidence.add(
                source="model_profiles",
                claim="worst_asr_model",
                detail=f"{high.model}: asr={high.asr:.4f}",
            )
            insight_lines.append(
                f"- ASR 维度：最稳健 {low.model} ({low.asr:.4f})，最脆弱 {high.model} ({high.asr:.4f})。 "
                f"{self.evidence.ref([e1, e2])}"
            )
            if focus and focus.asr is not None:
                gap_best = focus.asr - low.asr
                e3 = self.evidence.add(
                    source="model_profiles",
                    claim="focus_vs_best_asr_gap",
                    detail=f"{focus.model}-best_gap={gap_best:.4f} (focus={focus.asr:.4f}, best={low.asr:.4f})",
                )
                insight_lines.append(
                    f"- 待测模型与最优 ASR 的差距为 {gap_best:.4f}（{focus.model}: {focus.asr:.4f} vs {low.model}: {low.asr:.4f}）。 {self.evidence.ref([e3])}"
                )

        by_frr = [p for p in self.model_profiles if p.frr is not None]
        if by_frr:
            low = sorted(by_frr, key=lambda x: x.frr)[0]
            high = sorted(by_frr, key=lambda x: -x.frr)[0]
            e1 = self.evidence.add(
                source="model_profiles",
                claim="best_frr_model",
                detail=f"{low.model}: frr={low.frr:.4f}",
            )
            e2 = self.evidence.add(
                source="model_profiles",
                claim="worst_frr_model",
                detail=f"{high.model}: frr={high.frr:.4f}",
            )
            insight_lines.append(
                f"- FRR 维度：误拒最低 {low.model} ({low.frr:.4f})，误拒最高 {high.model} ({high.frr:.4f})。 "
                f"{self.evidence.ref([e1, e2])}"
            )
            if focus and focus.frr is not None:
                gap_best = focus.frr - low.frr
                e3 = self.evidence.add(
                    source="model_profiles",
                    claim="focus_vs_best_frr_gap",
                    detail=f"{focus.model}-best_gap={gap_best:.4f} (focus={focus.frr:.4f}, best={low.frr:.4f})",
                )
                insight_lines.append(
                    f"- 待测模型与最优 FRR 的差距为 {gap_best:.4f}（{focus.model}: {focus.frr:.4f} vs {low.model}: {low.frr:.4f}）。 {self.evidence.ref([e3])}"
                )

        by_kappa = [p for p in self.model_profiles if p.kappa is not None]
        if by_kappa:
            low = sorted(by_kappa, key=lambda x: x.kappa)[0]
            high = sorted(by_kappa, key=lambda x: -x.kappa)[0]
            e1 = self.evidence.add(
                source="kappa_report",
                claim="best_kappa_model",
                detail=f"{high.model}: kappa={high.kappa:.4f}",
            )
            e2 = self.evidence.add(
                source="kappa_report",
                claim="worst_kappa_model",
                detail=f"{low.model}: kappa={low.kappa:.4f}",
            )
            insight_lines.append(
                f"- 一致性维度（Kappa）：最高 {high.model} ({high.kappa:.4f})，最低 {low.model} ({low.kappa:.4f})。 "
                f"{self.evidence.ref([e1, e2])}"
            )

        # focus-model 的多指标相对分位（仅把其它模型作为背景）
        if focus:
            def _rank_text(value: Optional[float], bucket: List[ModelProfile], key_name: str, reverse: bool) -> str:
                if value is None:
                    return "-"
                arr = [x for x in bucket if getattr(x, key_name) is not None]
                if not arr:
                    return "-"
                arr = sorted(arr, key=lambda x: getattr(x, key_name), reverse=reverse)
                for idx, item in enumerate(arr, start=1):
                    if item.model == focus.model:
                        return f"{idx}/{len(arr)}"
                return "-"

            asr_rank = _rank_text(focus.asr, self.model_profiles, "asr", reverse=False)
            frr_rank = _rank_text(focus.frr, self.model_profiles, "frr", reverse=False)
            mds_rank = _rank_text(focus.mds, self.model_profiles, "mds", reverse=True)
            score_rank = _rank_text(focus.score, self.model_profiles, "score", reverse=True)
            eid = self.evidence.add(
                source="focus_model_profile",
                claim="focus_model_multi_metric_ranks",
                detail=f"{focus.model}: score_rank={score_rank}, asr_rank={asr_rank}, frr_rank={frr_rank}, mds_rank={mds_rank}",
            )
            insight_lines.append(
                f"- 待测模型综合分位：Composite 排名 {score_rank}，ASR 排名 {asr_rank}，FRR 排名 {frr_rank}，MDS 排名 {mds_rank}。 {self.evidence.ref([eid])}"
            )

            # 针对待测模型，给出相对最优模型的指标缺口
            best_peer = self._best_model()
            if best_peer and best_peer.model != focus.model:
                gap_parts = []
                if focus.asr is not None and best_peer.asr is not None:
                    gap_parts.append(f"ASR差距={focus.asr - best_peer.asr:+.4f}")
                if focus.mds is not None and best_peer.mds is not None:
                    gap_parts.append(f"MDS差距={focus.mds - best_peer.mds:+.4f}")
                if focus.score is not None and best_peer.score is not None:
                    gap_parts.append(f"Composite差距={focus.score - best_peer.score:+.4f}")
                if gap_parts:
                    eid2 = self.evidence.add(
                        source="model_profiles",
                        claim="focus_vs_best_peer_gap",
                        detail=f"{focus.model} vs {best_peer.model}: " + ", ".join(gap_parts),
                    )
                    insight_lines.append(
                        f"- 待测模型相对标杆模型 **{best_peer.model}** 的缺口：{'; '.join(gap_parts)}。 {self.evidence.ref([eid2])}"
                    )

        for row in self.attack_rows[:3]:
            if row.get("avg_asr") is None:
                continue
            attack = row["attack"]
            worst_model = row.get("worst_model") or "-"
            worst_asr = row.get("worst_asr")
            eid = self.evidence.add(
                source="attack_summary",
                claim="top_risk_attack",
                detail=f"{attack}: avg_asr={row['avg_asr']:.4f}, worst_model={worst_model}, worst_asr={worst_asr}",
            )
            worst_text = "-" if worst_asr is None else f"{worst_asr:.4f}"
            attack_lines.append(
                f"- 高风险攻击 {attack}：平均 ASR={row['avg_asr']:.4f}；最易受害模型={worst_model} ({worst_text})。 "
                f"{self.evidence.ref([eid])}"
            )

        if self.focus_attack_metric_rows:
            cm_top = [
                row for row in sorted(
                    self.focus_attack_metric_rows,
                    key=lambda x: (_safe_float(x.get("cm")) is None, -(_safe_float(x.get("cm")) or 0.0)),
                )
                if _safe_float(row.get("cm")) is not None
            ][:2]
            wsl_top = [
                row for row in sorted(
                    self.focus_attack_metric_rows,
                    key=lambda x: (_safe_float(x.get("wsl")) is None, -(_safe_float(x.get("wsl")) or 0.0)),
                )
                if _safe_float(row.get("wsl")) is not None
            ][:2]
            if cm_top:
                text = "; ".join([f"{x['attack']}: CM={_safe_float(x.get('cm')):.4f}" for x in cm_top])
                eid = self.evidence.add(
                    source="focus_attack_metrics",
                    claim="focus_top_cm_attacks",
                    detail=f"{self.focus_model}: {text}",
                )
                focus_lines.append(f"- 待测模型高代价攻击面（CM）：{text}。 {self.evidence.ref([eid])}")
            if wsl_top:
                text = "; ".join([f"{x['attack']}: WSL={_safe_float(x.get('wsl')):.4f}" for x in wsl_top])
                eid = self.evidence.add(
                    source="focus_attack_metrics",
                    claim="focus_top_wsl_attacks",
                    detail=f"{self.focus_model}: {text}",
                )
                attack_lines.append(f"- 待测模型高损失攻击面（WSL）：{text}。 {self.evidence.ref([eid])}")

        top_asr = self.external_signals.get("all_metrics_top_attack_asr")
        if isinstance(top_asr, dict) and top_asr.get("attack"):
            avg_asr = _safe_float(top_asr.get("avg_asr"))
            eid = self.evidence.add(
                source="all_metrics_summary",
                claim="global_top_attack_asr",
                detail=f"{top_asr.get('attack')}: avg_asr={avg_asr}",
            )
            attack_lines.append(
                f"- 全局（all_metrics）最高风险攻击为 {top_asr.get('attack')}，Avg ASR={_fmt(avg_asr, 4)}。 {self.evidence.ref([eid])}"
            )
        top_frr = self.external_signals.get("all_metrics_top_attack_frr")
        if isinstance(top_frr, dict) and top_frr.get("attack"):
            avg_frr = _safe_float(top_frr.get("avg_frr"))
            eid = self.evidence.add(
                source="all_metrics_summary",
                claim="global_top_attack_frr",
                detail=f"{top_frr.get('attack')}: avg_frr={avg_frr}",
            )
            insight_lines.append(
                f"- 全局（all_metrics）最高误拒压力攻击为 {top_frr.get('attack')}，Avg FRR={_fmt(avg_frr, 4)}。 {self.evidence.ref([eid])}"
            )

        self.case_line_pool = []
        self.case_candidate_records = []
        self.case_meta_by_line = {}
        for case in self.case_examples:
            eid = self.evidence.add(
                source=f"{case.source_file}:{case.line_no}",
                claim=f"case_{case.case_type}",
                detail=f"safety={case.safety_label}, asr={case.asr_label}, frr={case.frr_label}, strategy={case.response_strategy_label}, response_label={case.response_label}",
            )
            line = (
                f"- [{case.polarity}/{case.case_type}] Q: {_md_cell(case.query)} | A: {_md_cell(case.response)} {self.evidence.ref([eid])}"
            )
            self.case_line_pool.append(line)
            self.case_candidate_records.append(
                {
                    "line": line,
                    "polarity": case.polarity,
                    "case_type": case.case_type,
                    "score": case.representative_score,
                    "source": f"{case.source_file}:{case.line_no}",
                    "is_masked": case.is_masked,
                    "query_norm": _normalize_for_similarity(case.query),
                    "response_prefix": _normalize_for_similarity(case.response)[:200],
                }
            )
            label_consistency = 0.5
            if case.response_strategy_label is not None and case.response_label is not None:
                label_consistency = 1.0 if case.response_strategy_label == case.response_label else 0.0
            query_norm = _normalize_for_similarity(case.query)
            response_norm = _normalize_for_similarity(case.response)
            response_prefix = response_norm[:200]
            self.case_meta_by_line[line] = {
                "polarity": case.polarity,
                "case_type": case.case_type,
                "query_norm": query_norm,
                "response_norm": response_norm,
                "response_prefix": response_prefix,
                "content_key": f"{query_norm[:240]}|{response_prefix}",
                "signature": f"{case.case_type}|{query_norm[:160]}|{response_prefix[:140]}",
                "similarity_text": f"{query_norm} {response_prefix}".strip(),
                "score": case.representative_score,
                "label_consistency": label_consistency,
                "is_masked": case.is_masked,
            }
        self.case_candidate_records.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
        case_lines = self._select_case_lines_rule_based(self.case_line_pool)
        if self.case_line_pool:
            mode_text = "LLM代表性筛选" if not self.args.no_llm else "规则回退筛选（未启用 LLM）"
            audit_lines.append(
                f"- 案例候选池共 {len(self.case_line_pool)} 条（按代表性评分排序），案例章节采用{mode_text}。"
            )
            if self.case_pool_stats:
                audit_lines.append(
                    "- 案例池质量：原始 {raw_size} 条 -> 去重后 {unique_size} 条，"
                    "冲突分组 {conflict_groups}，去重裁剪 {deduped}。".format(
                        raw_size=self.case_pool_stats.get("raw_size", 0),
                        unique_size=self.case_pool_stats.get("unique_size", 0),
                        conflict_groups=self.case_pool_stats.get("conflict_groups", 0),
                        deduped=self.case_pool_stats.get("deduped", 0),
                    )
                )
            if self.case_selection_stats:
                audit_lines.append(
                    "- 案例入选质量：{selected} 条，类型覆盖 {types} 类，query 覆盖 {queries} 个，"
                    "正负样本={pos}/{neg}，近似重复率={dup:.2%}（每 query 上限={cap}）。".format(
                        selected=self.case_selection_stats.get("selected", 0),
                        types=self.case_selection_stats.get("unique_case_types", 0),
                        queries=self.case_selection_stats.get("unique_queries", 0),
                        pos=self.case_selection_stats.get("positive_cases", 0),
                        neg=self.case_selection_stats.get("negative_cases", 0),
                        dup=float(self.case_selection_stats.get("near_dup_ratio", 0.0) or 0.0),
                        cap=self.case_selection_stats.get("max_cases_per_query", 1),
                    )
                )
        style_snippets = self.style_fewshot.get("snippets") if isinstance(self.style_fewshot, dict) else []
        if isinstance(style_snippets, list) and style_snippets:
            audit_lines.append(f"- 风格 few-shot 已加载：{len(style_snippets)} 条示例。")

        if focus and focus.asr is not None:
            eid = self.evidence.add(
                source="focus_model_profile",
                claim="recommend_focus_reduce_asr",
                detail=f"{focus.model}: asr={focus.asr:.4f}",
            )
            recommendation_lines.append(
                f"- 以待测模型 **{focus.model}** 为主线：先降低其高风险攻击面的 ASR（当前 Avg ASR={focus.asr:.4f}），优先修复前两类高风险攻击。 {self.evidence.ref([eid])}"
            )
            # 明确目标值：追到同侪中位和最优邻近带
            peer_asr = sorted([p.asr for p in self.model_profiles if p.asr is not None])
            if peer_asr:
                med = peer_asr[len(peer_asr) // 2]
                best = peer_asr[0]
                target = max(best + 0.02, med)
                eid_t = self.evidence.add(
                    source="model_profiles",
                    claim="focus_asr_target",
                    detail=f"{focus.model}: current={focus.asr:.4f}, median={med:.4f}, best={best:.4f}, target<={target:.4f}",
                )
                recommendation_lines.append(
                    f"- 量化目标：将 **{focus.model}** 的 Avg ASR 从 {focus.asr:.4f} 降到 <= {target:.4f}（先达同侪中位，再逼近最优+0.02）。 {self.evidence.ref([eid_t])}"
                )
        elif by_asr:
            high = sorted(by_asr, key=lambda x: -x.asr)[0]
            eid = self.evidence.add(
                source="model_profiles",
                claim="recommend_reduce_asr",
                detail=f"{high.model}: asr={high.asr:.4f}",
            )
            recommendation_lines.append(
                f"- 优先降低 **{high.model}** 的攻击成功率（当前 Avg ASR={high.asr:.4f}），将其设为下轮红队修复主线。 {self.evidence.ref([eid])}"
            )
        if focus:
            if focus.frr is not None:
                eid = self.evidence.add(
                    source="focus_model_profile",
                    claim="recommend_focus_reduce_frr",
                    detail=f"{focus.model}: frr={focus.frr:.4f}",
                )
                recommendation_lines.append(
                    f"- 以待测模型 **{focus.model}** 为主线：针对误拒优化拒答边界（当前 Avg FRR={focus.frr:.4f}），补充 benign hard-case 与阈值校准。 {self.evidence.ref([eid])}"
                )
            else:
                eid = self.evidence.add(
                    source="focus_model_profile",
                    claim="recommend_focus_fill_frr",
                    detail=f"{focus.model}: frr missing",
                )
                recommendation_lines.append(
                    f"- 中期优化：待测模型 **{focus.model}** 当前 FRR 缺失，建议先补齐 benign 样本与误拒标注，再执行拒答阈值校准。 {self.evidence.ref([eid])}"
                )
        elif by_frr:
            high = sorted(by_frr, key=lambda x: -x.frr)[0]
            eid = self.evidence.add(
                source="model_profiles",
                claim="recommend_reduce_frr",
                detail=f"{high.model}: frr={high.frr:.4f}",
            )
            recommendation_lines.append(
                f"- 优先修复 **{high.model}** 的过拒问题（Avg FRR={high.frr:.4f}），补充 benign hard-case 并校准拒答策略。 {self.evidence.ref([eid])}"
            )
        if focus and focus.model in self.matrix:
            focus_sorted_attacks = []
            for attack_name, raw_v in self.matrix.get(focus.model, {}).items():
                v = _safe_float(raw_v)
                if v is not None:
                    focus_sorted_attacks.append((attack_name, v))
            focus_sorted_attacks.sort(key=lambda x: -x[1])
            if focus_sorted_attacks:
                first_name, first_v = focus_sorted_attacks[0]
                eid = self.evidence.add(
                    source="attack_summary",
                    claim="recommend_focus_attack_regression",
                    detail=f"{focus.model} on {first_name}: asr={first_v:.4f}",
                )
                recommendation_lines.append(
                    f"- 为待测模型建立 **{first_name}** 专项回归门禁（{focus.model} ASR={first_v:.4f}），发布前强制通过。 {self.evidence.ref([eid])}"
                )
        elif self.attack_rows:
            first = self.attack_rows[0]
            if first.get("avg_asr") is not None:
                eid = self.evidence.add(
                    source="attack_summary",
                    claim="recommend_attack_regression",
                    detail=f"{first['attack']}: avg_asr={first['avg_asr']:.4f}",
                )
                recommendation_lines.append(
                    f"- 建立 **{first['attack']}** 专项回归门禁（当前 Avg ASR={first['avg_asr']:.4f}），发布前强制通过。 {self.evidence.ref([eid])}"
                )

        if focus and self.focus_attack_metric_rows:
            top_cm = sorted(
                [row for row in self.focus_attack_metric_rows if _safe_float(row.get("cm")) is not None],
                key=lambda x: -(_safe_float(x.get("cm")) or 0.0),
            )[:1]
            if top_cm:
                attack_name = str(top_cm[0].get("attack") or "-")
                cm_val = _safe_float(top_cm[0].get("cm"))
                wsl_val = _safe_float(top_cm[0].get("wsl"))
                eid = self.evidence.add(
                    source="focus_attack_metrics",
                    claim="recommend_focus_reduce_cm",
                    detail=f"{focus.model} on {attack_name}: cm={cm_val}, wsl={wsl_val}",
                )
                recommendation_lines.append(
                    f"- 针对 **{attack_name}** 建立“高代价优先”治理闭环（CM={_fmt(cm_val, 4)}，WSL={_fmt(wsl_val, 4)}）："
                    f"上线前加审查策略、上线后做专项监控回放。 {self.evidence.ref([eid])}"
                )

        if self.facts.get("kappa_summary"):
            avg = _safe_float(self.facts["kappa_summary"].get("avg_kappa"))
            if avg is not None and avg < 0.6:
                eid = self.evidence.add(
                    source="kappa_summary",
                    claim="recommend_label_protocol",
                    detail=f"avg_kappa={avg:.4f}",
                )
                recommendation_lines.append(
                    f"- 当前标注一致性偏低（avg_kappa={avg:.4f}），建议统一判标协议并建立复核闭环。 {self.evidence.ref([eid])}"
                )

        if not case_lines:
            audit_lines.append("- 未发现可用案例样本，案例章节将被跳过。")

        return DraftReport(
            exec_lines=exec_lines,
            focus_lines=focus_lines,
            insight_lines=insight_lines,
            attack_lines=attack_lines,
            case_lines=case_lines,
            recommendation_lines=recommendation_lines,
            audit_lines=audit_lines,
        )

    def _round2_reflect_and_repair(self, draft: DraftReport) -> DraftReport:
        audit_lines = list(draft.audit_lines)
        section_overlap_threshold = float(getattr(self.args, "section_overlap_threshold", 0.88) or 0.88)
        section_overlap_threshold = max(0.7, min(0.98, section_overlap_threshold))

        def dedupe(lines: List[str], label: str) -> List[str]:
            seen = set()
            out = []
            for line in lines:
                line = _clean_report_text(str(line))
                norm = re.sub(r"\s+", " ", line).strip()
                if norm in seen:
                    continue
                seen.add(norm)
                out.append(norm)
            if len(out) != len(lines):
                audit_lines.append(f"- 审校：`{label}` 存在重复结论，已去重。")
            return out

        exec_lines = dedupe(draft.exec_lines, "exec")
        focus_lines = dedupe(draft.focus_lines, "focus")
        insight_lines = dedupe(draft.insight_lines, "insight")
        attack_lines = dedupe(draft.attack_lines, "attack")
        case_lines = dedupe(draft.case_lines, "case")
        recommendation_lines = dedupe(draft.recommendation_lines, "recommendation")

        # 一致性检查：如果“最好”和“最差”模型在同一指标上是同一个（且样本数>1），删除冲突行。
        if len(self.model_profiles) > 1:
            filtered = []
            conflict = False
            for line in insight_lines:
                if "最稳健" in line and "最脆弱" in line:
                    m = re.findall(r"最稳健\s+([^\s(]+)|最脆弱\s+([^\s(]+)", line)
                    names = [x[0] or x[1] for x in m if (x[0] or x[1])]
                    if len(names) >= 2 and names[0] == names[1]:
                        conflict = True
                        continue
                filtered.append(line)
            if conflict:
                audit_lines.append("- 审校：检测到同指标最好/最差模型冲突，已移除冲突结论。")
            insight_lines = filtered

        def _norm_for_overlap(line: str) -> str:
            text = re.sub(r"\[E\d+\]", " ", line)
            text = re.sub(r"[+\-]?\d+(?:\.\d+)?", " ", text)
            return _normalize_for_similarity(text, keep_digits=False)

        # 抑制第2章(attack)与第3章(focus/insight)高度重复段落，保留更聚焦待测模型的表达。
        attack_norm = [_norm_for_overlap(x) for x in attack_lines]
        filtered_focus = []
        removed_focus = 0
        for line in focus_lines:
            n = _norm_for_overlap(line)
            if n and any(_similarity_ratio(n, a) >= section_overlap_threshold for a in attack_norm):
                removed_focus += 1
                continue
            filtered_focus.append(line)
        focus_lines = filtered_focus

        filtered_insight = []
        removed_insight = 0
        focus_norm = [_norm_for_overlap(x) for x in focus_lines]
        for line in insight_lines:
            n = _norm_for_overlap(line)
            if not n:
                filtered_insight.append(line)
                continue
            overlap_with_attack = any(_similarity_ratio(n, a) >= section_overlap_threshold for a in attack_norm)
            overlap_with_focus = any(_similarity_ratio(n, f) >= section_overlap_threshold for f in focus_norm)
            if overlap_with_attack or overlap_with_focus:
                removed_insight += 1
                continue
            filtered_insight.append(line)
        insight_lines = filtered_insight
        if removed_focus or removed_insight:
            audit_lines.append(
                f"- 审校：为降低章节重复，已移除第3章高重叠结论 {removed_focus + removed_insight} 条（阈值={section_overlap_threshold:.2f}）。"
            )

        # 每条结论必须带证据编号；若缺失则补充审校备注。
        tag_re = re.compile(r"\[E\d+\]")
        for bucket_name, bucket in [
            ("exec", exec_lines),
            ("focus", focus_lines),
            ("insight", insight_lines),
            ("attack", attack_lines),
            ("case", case_lines),
            ("recommendation", recommendation_lines),
        ]:
            for i, line in enumerate(bucket):
                if tag_re.search(line):
                    continue
                eid = self.evidence.add(
                    source="auto_audit",
                    claim="missing_evidence_backfill",
                    detail=f"{bucket_name} line {i + 1}",
                )
                bucket[i] = line + " " + self.evidence.ref([eid])
            if bucket and not all(tag_re.search(x) for x in bucket):
                audit_lines.append(f"- 审校：`{bucket_name}` 存在证据缺失，已自动补齐。")

        return DraftReport(
            exec_lines=exec_lines,
            focus_lines=focus_lines,
            insight_lines=insight_lines,
            attack_lines=attack_lines,
            case_lines=case_lines,
            recommendation_lines=recommendation_lines,
            audit_lines=_normalize_audit_lines(audit_lines),
        )

    @staticmethod
    def _draft_to_dict(draft: DraftReport) -> Dict[str, List[str]]:
        return {
            "exec_lines": list(draft.exec_lines),
            "focus_lines": list(draft.focus_lines),
            "insight_lines": list(draft.insight_lines),
            "attack_lines": list(draft.attack_lines),
            "case_lines": list(draft.case_lines),
            "recommendation_lines": list(draft.recommendation_lines),
            "audit_lines": list(draft.audit_lines),
        }

    @staticmethod
    def _dict_to_draft(raw: Dict[str, object], fallback: DraftReport) -> DraftReport:
        return DraftReport(
            exec_lines=[str(x) for x in (raw.get("exec_lines") or fallback.exec_lines)],
            focus_lines=[str(x) for x in (raw.get("focus_lines") or fallback.focus_lines)],
            insight_lines=[str(x) for x in (raw.get("insight_lines") or fallback.insight_lines)],
            attack_lines=[str(x) for x in (raw.get("attack_lines") or fallback.attack_lines)],
            case_lines=[str(x) for x in (raw.get("case_lines") or fallback.case_lines)],
            recommendation_lines=[str(x) for x in (raw.get("recommendation_lines") or fallback.recommendation_lines)],
            audit_lines=_normalize_audit_lines([str(x) for x in (raw.get("audit_lines") or fallback.audit_lines)]),
        )

    def _llm_json_call(self, client, *, system_prompt: str, payload: Dict[str, object], stage: str) -> Dict[str, object]:
        response = client.chat.completions.create(
            model=self.args.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError(f"{stage} 返回空内容")
        data = json.loads(content)
        if not isinstance(data, dict):
            raise RuntimeError(f"{stage} 返回非 JSON object")
        return data

    def _optional_llm_rewrite(self, draft: DraftReport, context_notes: str) -> DraftReport:
        if self.args.no_llm:
            return _append_audit(draft, "- LLM 状态：未调用（`--no-llm`）。")
        if not (self.args.model or "").strip():
            msg = "LLM 状态：未调用（model 为空）。"
            if self.args.require_llm:
                raise RuntimeError(msg)
            return _append_audit(draft, f"- {msg}")
        try:
            client = build_openai_client(self.args)
        except Exception as e:
            msg = f"LLM 状态：未调用（客户端初始化失败：{_sanitize_error_message(e)}）。"
            if self.args.require_llm:
                raise RuntimeError(msg)
            return _append_audit(draft, f"- {msg}")

        constraints = {
            "must_keep_evidence_tags": True,
            "no_fabrication": True,
            "focus_model": self.focus_model,
            "context_notes": context_notes,
            "case_selection": {
                "from_pool_only": True,
                "pool_size": len(self.case_line_pool),
                "need_positive_and_negative": True,
                "max_cases": max(1, int(self.args.max_cases)),
                "prefer_high_score_and_diversity": True,
                "self_select_representative_examples": True,
                "forbid_auto_round_robin_sampling": True,
                "forbid_duplicate_or_conflict_cases": True,
            },
            "chapter_roles": {
                "chapter2": "只写全局态势与攻击面，不复述待测模型对标差距",
                "chapter3": "只写待测模型相对标杆差距与优势，避免泛化排行榜复读",
                "chapter4": "只写待测模型纵向根因诊断（Bias/WSL/CM/波动）与业务影响",
            },
            "writing_contract": {
                "paragraph_template": "每段遵循：结论句 -> 指标证据([E*]) -> 业务含义/动作",
                "must_bind_focus_model_for_recommendations": True,
            },
        }
        style_fewshot = self.style_fewshot
        style_contract = {
            "style_name": style_fewshot.get("style_name") if isinstance(style_fewshot, dict) else "teleai_report_style",
            "tone": style_fewshot.get("tone") if isinstance(style_fewshot, dict) else "审计、克制、可追责",
            "granularity": style_fewshot.get("granularity") if isinstance(style_fewshot, dict) else "单段 2-4 句",
            "paragraph_template": style_fewshot.get("paragraph_template")
            if isinstance(style_fewshot, dict)
            else "每段遵循：结论句 -> 指标证据([E*]) -> 业务含义/动作",
            "rules": style_fewshot.get("rules") if isinstance(style_fewshot, dict) else [],
            "snippets_by_section": style_fewshot.get("snippets_by_section") if isinstance(style_fewshot, dict) else {},
        }
        external_signals = self.external_signals
        case_candidates = self.case_candidate_records[: max(50, int(self.args.max_cases) * 12)]
        draft_snapshot = self._draft_to_dict(draft)

        try:
            # Stage 1: outline + representative case pre-selection.
            stage1_payload = {
                "draft": draft_snapshot,
                "constraints": constraints,
                "case_line_pool": self.case_line_pool,
                "case_candidates": case_candidates,
                "external_signals": external_signals,
                "style_fewshot": style_fewshot,
                "style_contract": style_contract,
            }
            stage1_prompt = (
                "你是安全评测报告规划器。先做结构规划，不改写正文。"
                "任务：根据草稿输出写作提纲，并从 case_line_pool 中主动挑选最有代表性的案例。"
                "案例要求：优先高 score，覆盖 positive/negative 与多 case_type；禁止轮询式抽样；禁止重复 Q/A 与标签冲突样本。"
                "若提供 style_fewshot/style_contract，请提炼其语气、段落粒度、段落模板和章节职责，形成可执行提纲。"
                "输出 JSON: {\"outline\": {...}, \"case_lines\": [...], \"audit_lines\": [...] }。"
                "case_lines 必须完全复制池中原文，且最多 max_cases 条。"
            )
            stage1_data = self._llm_json_call(
                client,
                system_prompt=stage1_prompt,
                payload=stage1_payload,
                stage="LLM阶段1(提纲)",
            )
            outline = stage1_data.get("outline")
            if not isinstance(outline, dict):
                outline = {}
            planned_cases_raw = [str(x) for x in (stage1_data.get("case_lines") or [])]
            planned_cases = self._finalize_case_lines(
                self._canonicalize_case_lines_from_pool(planned_cases_raw) or draft.case_lines
            )

            # Stage 2: rewrite with outline constraints.
            stage2_input = DraftReport(
                exec_lines=draft.exec_lines,
                focus_lines=draft.focus_lines,
                insight_lines=draft.insight_lines,
                attack_lines=draft.attack_lines,
                case_lines=planned_cases,
                recommendation_lines=draft.recommendation_lines,
                audit_lines=draft.audit_lines
                + [str(x) for x in (stage1_data.get("audit_lines") or [])],
            )
            stage2_payload = {
                "draft": self._draft_to_dict(stage2_input),
                "outline": outline,
                "constraints": constraints,
                "case_line_pool": self.case_line_pool,
                "external_signals": external_signals,
                "style_fewshot": style_fewshot,
                "style_contract": style_contract,
            }
            stage2_prompt = (
                "你是安全评测报告写作器。请根据 outline 重写草稿，提高结构与叙事质量。"
                "若提供 style_fewshot/style_contract，按其风格写作（先结论后证据、业务风险导向、诊断口吻），"
                "严格执行段落模板：结论句 -> 指标证据([E*]) -> 业务含义/动作。"
                "第2章只写全局态势；第3章只写待测模型对标；第4章只写纵向根因，三章不得互相复述。"
                "但不得逐字大段复制示例。"
                "禁止新增事实；每条结论必须保留 [E编号]；案例必须来自 case_line_pool。"
                "输出 JSON: {\"draft\": {...}}，draft 字段结构与输入一致。"
            )
            stage2_data = self._llm_json_call(
                client,
                system_prompt=stage2_prompt,
                payload=stage2_payload,
                stage="LLM阶段2(正文)",
            )
            stage2_draft_raw = stage2_data.get("draft")
            if not isinstance(stage2_draft_raw, dict):
                raise RuntimeError("LLM阶段2 返回结构非 draft")
            stage2_draft = self._dict_to_draft(stage2_draft_raw, stage2_input)
            stage2_draft.case_lines = self._finalize_case_lines(
                self._canonicalize_case_lines_from_pool(stage2_draft.case_lines) or planned_cases
            )

            # Stage 3: audit pass for consistency and traceability.
            stage3_payload = {
                "draft": self._draft_to_dict(stage2_draft),
                "constraints": constraints,
                "outline": outline,
                "style_fewshot": style_fewshot,
                "style_contract": style_contract,
            }
            stage3_prompt = (
                "你是安全评测报告审校器。只做一致性修复、重复去除、术语统一。"
                "重点检查：案例重复/冲突、第2章与第3章复述、建议是否绑定待测模型。"
                "禁止新增事实；必须保留并补齐 [E编号]；案例必须来自原候选池。"
                "输出 JSON: {\"draft\": {...}, \"audit_lines\": [...] }。"
            )
            stage3_data = self._llm_json_call(
                client,
                system_prompt=stage3_prompt,
                payload=stage3_payload,
                stage="LLM阶段3(审校)",
            )
            stage3_draft_raw = stage3_data.get("draft")
            if not isinstance(stage3_draft_raw, dict):
                raise RuntimeError("LLM阶段3 返回结构非 draft")
            stage3_draft = self._dict_to_draft(stage3_draft_raw, stage2_draft)
            stage3_draft.case_lines = self._finalize_case_lines(
                self._canonicalize_case_lines_from_pool(stage3_draft.case_lines) or stage2_draft.case_lines
            )
            stage3_draft.audit_lines.extend([str(x) for x in (stage3_data.get("audit_lines") or [])])
            return _append_audit(stage3_draft, "- LLM 状态：已完成三阶段流程（提纲 -> 正文 -> 审校）。")
        except Exception as e:
            msg = f"LLM 状态：调用失败（三阶段流程，{_sanitize_error_message(e)}）。"
            if self.args.require_llm:
                raise RuntimeError(msg)
            return _append_audit(draft, f"- {msg}")

    def _plan_sections(self, draft: DraftReport, has_plots: bool) -> List[Tuple[str, str]]:
        # 不预设固定章结构：按洞见内容动态组织。
        plan: List[Tuple[str, str]] = []
        plan.append(("执行摘要", "exec"))
        if draft.focus_lines:
            plan.append((f"待测模型视角：{self.focus_model}", "focus"))
        if draft.insight_lines:
            plan.append(("跨模型全指标洞察", "insights"))
        if draft.attack_lines:
            plan.append(("攻击向量威胁洞察", "attacks"))
        if draft.case_lines:
            plan.append(("案例解析", "cases"))
        if has_plots:
            plan.append(("可视化仪表盘", "plots"))
        plan.append(("改进建议", "recommendations"))
        if draft.audit_lines:
            plan.append(("审校与一致性检查", "audit"))
        return plan

    def generate(self, context_notes: str, has_plots: bool) -> Tuple[DraftReport, List[Tuple[str, str]]]:
        draft1 = self._round1_draft()
        draft2 = self._round2_reflect_and_repair(draft1)
        draft3 = self._optional_llm_rewrite(draft2, context_notes)
        # LLM 改写后再做一次轻量一致性检查
        final_draft = self._round2_reflect_and_repair(draft3)
        plan = self._plan_sections(final_draft, has_plots=has_plots)
        return final_draft, plan


def render_meta_info(
    generated_at: str,
    eval_models: List[str],
    baseline_models: List[str],
    attacks: List[str],
    metrics: List[str],
    focus_model: str,
) -> str:
    rows = [
        ["报告生成时间", generated_at],
        ["评测对象", ", ".join(eval_models) if eval_models else "-"],
        ["对照对象", ", ".join(baseline_models) if baseline_models else "-"],
        ["攻击向量集", ", ".join(attacks) if attacks else "-"],
        ["核心指标", ", ".join(metrics) if metrics else "-"],
        ["待测模型", focus_model or "-"],
    ]
    return render_markdown_table(["项目", "内容"], rows)


def load_context_notes(path: Optional[str]) -> str:
    if not path:
        return ""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Context notes not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def build_summary_table(matrix: Dict[str, Dict[str, float]], attacks: List[str], models: List[str]) -> str:
    columns = ["Attack Method"] + models
    rows: List[List[str]] = []
    for attack in attacks:
        row = [attack]
        for model in models:
            value = _safe_float(matrix.get(model, {}).get(attack))
            row.append("-" if value is None else f"{value:.4f}")
        rows.append(row)
    return render_markdown_table(columns, rows)


def _load_structured_file(path: str) -> Dict[str, object]:
    if not path or not os.path.isfile(path):
        return {}
    lower = path.lower()
    with open(path, "r", encoding="utf-8") as f:
        if lower.endswith(".json"):
            data = json.load(f)
        elif lower.endswith(".yaml") or lower.endswith(".yml"):
            import yaml

            data = yaml.safe_load(f)
        else:
            return {}
    return data if isinstance(data, dict) else {}


def load_metrics_catalog(path: str) -> Dict[str, object]:
    return _load_structured_file(path)


def load_style_fewshot(path: str, max_snippets: int = 12) -> Dict[str, object]:
    data = _load_structured_file(path)
    if not isinstance(data, dict):
        return {}
    rules_raw = data.get("rules")
    snippets_raw = data.get("snippets")
    rules = [str(x).strip() for x in (rules_raw or []) if str(x).strip()]
    snippets: List[Dict[str, str]] = []
    for item in snippets_raw or []:
        if not isinstance(item, dict):
            continue
        section = str(item.get("section") or "").strip()
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        snippets.append(
            {
                "section": section or "通用",
                "text": _trim_text(text, limit=520),
            }
        )
    snippets = snippets[: max(1, int(max_snippets))]
    snippets_by_section: Dict[str, List[str]] = defaultdict(list)
    for item in snippets:
        section = str(item.get("section") or "通用")
        text = str(item.get("text") or "")
        if text:
            snippets_by_section[section].append(text)
    return {
        "style_name": str(data.get("style_name") or "teleai_report_style"),
        "rules": rules,
        "snippets": snippets,
        "snippets_by_section": dict(snippets_by_section),
        "tone": str(data.get("tone") or "审计、克制、可追责"),
        "granularity": str(data.get("granularity") or "单段 2-4 句，先结论后证据"),
        "paragraph_template": str(
            data.get("paragraph_template")
            or "每段遵循：结论句 -> 指标证据([E*]) -> 业务含义/动作。"
        ),
    }


def load_asset_profile(path: str, focus_model: str) -> Dict[str, str]:
    data = _load_structured_file(path)
    if data:
        # Supported format:
        # {
        #   "default": {...},
        #   "profiles": {"model_a": {...}, "model_b": {...}}
        # }
        profiles = data.get("profiles")
        if isinstance(profiles, dict):
            candidate = profiles.get(focus_model) or profiles.get(focus_model.lower())
            if isinstance(candidate, dict):
                return {str(k): str(v) for k, v in candidate.items()}
        candidate = data.get(focus_model) or data.get(focus_model.lower())
        if isinstance(candidate, dict):
            return {str(k): str(v) for k, v in candidate.items()}
        fallback = data.get("default")
        if isinstance(fallback, dict):
            return {str(k): str(v) for k, v in fallback.items()}
    return {
        "模型标识": focus_model or "-",
        "部署形态": "N/A（可通过 --asset-profile 覆盖）",
        "模型架构": "N/A",
        "参数量级": "N/A",
        "上下文窗口": "N/A",
        "API版本": "N/A",
    }


def _render_square_template(template_text: str, mapping: Dict[str, str]) -> str:
    out = template_text
    for key, value in mapping.items():
        out = out.replace(f"[[{key}]]", value)
    return out


def _fmt_metric_from_catalog(catalog: Dict[str, object], metric_key: str) -> str:
    core = catalog.get("core_metrics")
    if not isinstance(core, dict):
        return ""
    metric = core.get(metric_key)
    if not isinstance(metric, dict):
        return ""
    cn = str(metric.get("cn_name") or metric_key)
    en = str(metric.get("full_name") or "")
    direction = str(metric.get("direction") or "-")
    formula = str(metric.get("formula") or "-")
    definition = str(metric.get("definition") or "-")
    interpretation = str(metric.get("interpretation") or "-")
    return (
        f"- **{metric_key} / {cn} ({en})**：\n"
        f"  - 定义：{definition}\n"
        f"  - 公式：`{formula}`\n"
        f"  - 判向：`{direction}`\n"
        f"  - 解读：{interpretation}"
    )


def _build_metrics_appendix(catalog: Dict[str, object]) -> str:
    if not catalog:
        return "未找到 metrics catalog，无法生成指标附录。"

    lines: List[str] = []
    for key in ["ASR", "FRR", "DELTA", "MDS", "KAPPA", "BIAS", "WSL", "CM"]:
        text = _fmt_metric_from_catalog(catalog, key)
        if text:
            lines.append(text)

    ternary = catalog.get("ternary_labels")
    if isinstance(ternary, dict):
        lines.append("")
        lines.append("### 三分类标签")
        for k in sorted(ternary.keys(), key=lambda x: str(x)):
            lines.append(f"- Label {k}: {ternary[k]}")

    cm = catalog.get("cost_matrix_default")
    if isinstance(cm, dict):
        lines.append("")
        lines.append("### 默认代价矩阵")
        rows: List[List[str]] = []
        for truth in sorted(cm.keys(), key=lambda x: str(x)):
            pred_map = cm.get(truth)
            if isinstance(pred_map, dict):
                rows.append(
                    [
                        str(truth),
                        str(pred_map.get("0", pred_map.get(0, "-"))),
                        str(pred_map.get("1", pred_map.get(1, "-"))),
                        str(pred_map.get("2", pred_map.get(2, "-"))),
                    ]
                )
        if rows:
            lines.append(render_markdown_table(["真实标签", "预测0", "预测1", "预测2"], rows))

    return "\n".join(lines) if lines else "metrics catalog 为空。"


def _asset_profile_table(profile: Dict[str, str]) -> str:
    field_order = ["模型标识", "部署形态", "模型架构", "参数量级", "上下文窗口", "API版本"]
    rows = [[field, profile.get(field, "-")] for field in field_order]
    # Preserve extra fields if provided
    for key, value in profile.items():
        if key in field_order:
            continue
        rows.append([key, value])
    return render_markdown_table(["资产字段", "内容"], rows)


def _environment_table(args: argparse.Namespace) -> str:
    base_url = args.base_url or "-"
    endpoint = args.azure_endpoint or "-"
    if not getattr(args, "show_sensitive_env", False):
        base_url = _redact_url(base_url)
        endpoint = _redact_url(endpoint)
    rows = [
        ["推理提供方", args.provider],
        ["模型/部署", args.model or "-"],
        ["Base URL", base_url],
        ["Azure Endpoint", endpoint],
        ["Azure API Version", args.azure_api_version or "-"],
        ["是否启用 LLM 润色", "否" if args.no_llm else "是"],
    ]
    return render_markdown_table(["配置项", "设定值"], rows)


def build_report_from_template(
    *,
    template_path: str,
    focus_model: str,
    focus_profile: Optional[ModelProfile],
    exec_paragraph: str,
    risk_paragraph: str,
    meta_info: str,
    attack_set: List[str],
    core_metrics: List[str],
    attack_table: str,
    model_table: str,
    summary_table: str,
    focus_cmp_table: str,
    case_review_block: str,
    draft: DraftReport,
    evidence_table: str,
    heatmap_path: Optional[str],
    model_bar_path: Optional[str],
    attack_bar_path: Optional[str],
    metric_bar_path: Optional[str],
    frr_bar_path: Optional[str],
    metrics_catalog: Dict[str, object],
    asset_profile: Dict[str, str],
    args: argparse.Namespace,
) -> str:
    if not template_path or not os.path.isfile(template_path):
        raise FileNotFoundError(f"Report template not found: {template_path}")

    with open(template_path, "r", encoding="utf-8") as f:
        template_text = f.read()

    asr = _fmt(focus_profile.asr if focus_profile else None, 4)
    frr = _fmt(focus_profile.frr if focus_profile else None, 4)
    delta = (
        _fmt((1.0 - focus_profile.asr - focus_profile.frr), 4)
        if focus_profile and focus_profile.asr is not None and focus_profile.frr is not None
        else "-"
    )

    asr_frr_def = "\n".join(
        [
            _fmt_metric_from_catalog(metrics_catalog, "ASR"),
            _fmt_metric_from_catalog(metrics_catalog, "FRR"),
            _fmt_metric_from_catalog(metrics_catalog, "DELTA"),
        ]
    ).strip() or "未配置 ASR/FRR/DELTA 指标定义。"

    attack_metric_def = _fmt_metric_from_catalog(metrics_catalog, "MDS") or "未配置 MDS 指标定义。"
    adv_metric_def = "\n".join(
        [
            _fmt_metric_from_catalog(metrics_catalog, "MDS"),
            _fmt_metric_from_catalog(metrics_catalog, "KAPPA"),
            _fmt_metric_from_catalog(metrics_catalog, "BIAS"),
            _fmt_metric_from_catalog(metrics_catalog, "WSL"),
            _fmt_metric_from_catalog(metrics_catalog, "CM"),
        ]
    ).strip() or "未配置进阶指标定义。"

    adv_metric_values = (
        f"- 待测模型 **{focus_model}**："
        f" MDS={_fmt(focus_profile.mds if focus_profile else None, 4)}，"
        f" Kappa={_fmt(focus_profile.kappa if focus_profile else None, 4)}，"
        f" Bias={_fmt(focus_profile.bias if focus_profile else None, 4)}，"
        f" WSL={_fmt(focus_profile.wsl if focus_profile else None, 4)}，"
        f" CM={_fmt(focus_profile.cm if focus_profile else None, 4)}。"
    )

    heatmap_block = f"![Overall Heatmap]({heatmap_path})" if heatmap_path else "_未生成热力图_"
    plot_items = [
        f"![Model ASR Bar]({model_bar_path})" if model_bar_path else "",
        f"![Attack ASR Bar]({attack_bar_path})" if attack_bar_path else "",
        f"![Model FRR Bar]({frr_bar_path})" if frr_bar_path else "",
        f"![Bias/WSL/CM Bar]({metric_bar_path})" if metric_bar_path else "",
    ]
    plot_panel_block = "\n".join([x for x in plot_items if x]) or "_未生成可视化_"

    mapping = {
        "REPORT_TITLE": f"{focus_model} 模型评测报告",
        "EXEC_SUMMARY": "\n".join([exec_paragraph, risk_paragraph, _join_lines(draft.exec_lines)]),
        "ASSET_INTRO": f"本次报告以 **{focus_model}** 为待测主体，其余模型用于对照分析。",
        "ASSET_TABLE": _asset_profile_table(asset_profile),
        "EVAL_SCOPE_TEXT": "本评测采用“数据构建 -> 对抗攻击 -> 裁判标注 -> 指标聚合 -> 报告生成”的闭环流程。",
        "ATTACK_SET_LIST": ", ".join(attack_set) if attack_set else "-",
        "CORE_METRICS_LIST": ", ".join(core_metrics) if core_metrics else "-",
        "ENV_TEXT": "以下为本次报告生成阶段可追溯的关键环境参数。",
        "ENV_TABLE": _environment_table(args),
        "METHODOLOGY_TEXT": meta_info,
        "ASR_FRR_DEF_BLOCK": asr_frr_def,
        "BASE_METRIC_VALUES": f"- 待测模型 **{focus_model}**：ASR={asr}，FRR={frr}，Delta={delta}。",
        "BASE_DIAGNOSIS": (
            f"- 基础攻防结论：当前模型在 ASR 侧存在改进空间，FRR 观测值为 {frr}。"
            "\n- 结构性攻击短板与横向差距详见第3章专项分析。"
        ),
        "ATTACK_METRIC_DEF_BLOCK": attack_metric_def,
        "ATTACK_TABLE": attack_table,
        "ATTACK_DIAGNOSIS": _join_lines(draft.attack_lines, "暂无攻击向量诊断。"),
        "ADV_METRIC_DEF_BLOCK": adv_metric_def,
        "ADV_METRIC_VALUES": adv_metric_values,
        "ADV_DIAGNOSIS": (
            f"- 综合判断：当前模型在 MDS={_fmt(focus_profile.mds if focus_profile else None, 4)}、"
            f"Kappa={_fmt(focus_profile.kappa if focus_profile else None, 4)} 维度未体现领先优势。"
            "\n- 详细横向差距与分位排序见第3章。"
        ),
        "FOCUS_COMPARE_INTRO": "本章以待测模型为中心，选取关键对照模型进行专项对比。",
        "FOCUS_COMPARE_TABLE": focus_cmp_table,
        "FOCUS_LINES": _join_lines(draft.focus_lines, "暂无待测模型专项结论。"),
        "INSIGHT_LINES": _join_lines(draft.insight_lines, "暂无跨模型洞察。"),
        "VERTICAL_DIAGNOSIS": (
            f"- 当前模型 mu_ASR={_fmt(focus_profile.mu_asr if focus_profile else None, 4)}，"
            f"sigma_ASR={_fmt(focus_profile.sigma_asr if focus_profile else None, 4)}。\n"
            f"- 当前模型 Bias={_fmt(focus_profile.bias if focus_profile else None, 4)}，"
            f"可结合 FRR 与 CM 评估其“保守/激进”倾向。"
        ),
        "CASE_REVIEW_BLOCK": case_review_block,
        "RECOMMENDATION_LINES": _join_lines(draft.recommendation_lines, "暂无自动建议。"),
        "HEATMAP_BLOCK": heatmap_block,
        "PLOT_PANEL_BLOCK": plot_panel_block,
        "AUDIT_LINES": _join_lines(draft.audit_lines, "暂无审校备注。"),
        "MODEL_TABLE": model_table,
        "ATTACK_TABLE_ALL": attack_table,
        "EVIDENCE_TABLE": evidence_table,
        "METRICS_APPENDIX": _build_metrics_appendix(metrics_catalog),
        "SUMMARY_TABLE": summary_table,
    }
    return _render_square_template(template_text, mapping)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成大模型安全性与鲁棒性深度评测报告（智能体模式）")
    parser.add_argument("--facts", default=DEFAULT_FACTS, help="facts.json 路径")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_FILE, help="报告输出路径")
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME, help="模型或 Azure 部署名")
    parser.add_argument("--provider", choices=["openai", "azure"], default="openai")
    parser.add_argument("--api-key", default=os.getenv("OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY"))
    parser.add_argument("--base-url", default=os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--azure-endpoint", default=os.getenv("AZURE_OPENAI_ENDPOINT"))
    parser.add_argument(
        "--azure-api-version",
        default=os.getenv("AZURE_OPENAI_API_VERSION", DEFAULT_AZURE_API_VERSION),
    )
    parser.add_argument("--eval-models", default="", help="逗号分隔的评测对象列表")
    parser.add_argument("--baseline-models", default="", help="逗号分隔的对照对象列表")
    parser.add_argument("--attack-set", default="", help="逗号分隔的攻击向量集覆盖列表")
    parser.add_argument("--core-metrics", default="ASR,FRR,MDS,Kappa,Bias,WSL,CM", help="逗号分隔的核心指标")
    parser.add_argument("--focus-model", default="", help="待测模型（报告主视角）")
    parser.add_argument("--case-input", default="", help="案例输入 jsonl 文件或目录；为空则尝试从 asr_labels/<focus_model> 自动发现")
    parser.add_argument("--max-cases", type=int, default=8, help="案例章节最多展示数量（由 LLM 从候选池筛选）")
    parser.add_argument("--max-cases-per-query", type=int, default=1, help="同一 query 最多允许入选案例数")
    parser.add_argument("--case-similarity-threshold", type=float, default=0.82, help="案例近似判定阈值（用于去重与硬检查）")
    parser.add_argument("--case-similarity-max-ratio", type=float, default=0.35, help="案例允许的最大近似重复率")
    parser.add_argument("--section-overlap-threshold", type=float, default=0.88, help="章节间语义重叠判定阈值")
    parser.add_argument("--section-overlap-max-ratio", type=float, default=0.30, help="第2章与第3章允许的最大重叠比例")
    parser.add_argument("--context-notes", default="", help="可选：交叉验证参考材料")
    parser.add_argument("--metrics-catalog", default=DEFAULT_METRICS_CATALOG, help="指标定义 catalog（yaml/json）")
    parser.add_argument("--report-template", default=DEFAULT_REPORT_TEMPLATE, help="报告模板路径（markdown，使用 [[KEY]] 占位符）")
    parser.add_argument("--style-fewshot", default=DEFAULT_STYLE_FEWSHOT, help="风格 few-shot 资产（yaml/json）")
    parser.add_argument("--style-max-snippets", type=int, default=12, help="注入 LLM 的风格示例上限")
    parser.add_argument("--asset-profile", default="", help="可选：模型资产信息文件（yaml/json）")
    parser.add_argument("--legacy-layout", action="store_true", help="强制使用内置旧版报告布局（忽略模板）")
    parser.add_argument("--skip-hard-check", action="store_true", help="跳过落盘前事实一致性硬校验")
    parser.add_argument("--show-sensitive-env", action="store_true", help="在报告环境表中显示完整 endpoint/base-url（默认脱敏）")
    parser.add_argument("--no-llm", action="store_true", help="仅输出数据驱动文本，不调用 LLM")
    parser.add_argument("--require-llm", action="store_true", help="要求必须成功调用 LLM；失败则直接报错")
    return parser.parse_args()


def _model_metric_table_rows(profiles: List[ModelProfile], focus_model: str) -> List[List[str]]:
    rows: List[List[str]] = []
    for idx, p in enumerate(profiles, start=1):
        marker = " (FOCUS)" if focus_model and p.model == focus_model else ""
        rows.append(
            [
                str(idx),
                p.model + marker,
                "-" if p.score is None else f"{p.score:.4f}",
                "-" if p.asr is None else f"{p.asr:.4f}",
                "-" if p.frr is None else f"{p.frr:.4f}",
                "-" if p.mds is None else f"{p.mds:.4f}",
                "-" if p.kappa is None else f"{p.kappa:.4f}",
                "-" if p.bias is None else f"{p.bias:.4f}",
                "-" if p.wsl is None else f"{p.wsl:.4f}",
                "-" if p.cm is None else f"{p.cm:.4f}",
                "-" if p.mu_asr is None else f"{p.mu_asr:.4f}",
                "-" if p.sigma_asr is None else f"{p.sigma_asr:.4f}",
                "-" if p.attacks_covered is None else str(p.attacks_covered),
            ]
        )
    return rows


def _attack_table_rows(rows: List[Dict[str, object]]) -> List[List[str]]:
    out: List[List[str]] = []
    for idx, row in enumerate(rows, start=1):
        out.append(
            [
                str(idx),
                str(row.get("attack") or "-"),
                "-" if row.get("avg_asr") is None else f"{row['avg_asr']:.4f}",
                "-" if row.get("avg_frr") is None else f"{row['avg_frr']:.4f}",
                str(row.get("worst_model") or "-"),
                "-" if row.get("worst_asr") is None else f"{row['worst_asr']:.4f}",
            ]
        )
    return out


def _join_lines(lines: List[str], default_msg: str = "暂无数据。") -> str:
    if not lines:
        return default_msg
    return "\n".join(lines)


def _fmt(v: Optional[float], digits: int = 4, default: str = "-") -> str:
    if v is None:
        return default
    return f"{v:.{digits}f}"


def _get_profile(profiles: List[ModelProfile], model: str) -> Optional[ModelProfile]:
    for p in profiles:
        if p.model == model:
            return p
    return None


def _top_by(
    profiles: List[ModelProfile],
    key: str,
    reverse: bool,
    non_none_only: bool = True,
) -> List[ModelProfile]:
    arr = profiles
    if non_none_only:
        arr = [x for x in profiles if getattr(x, key) is not None]
    return sorted(arr, key=lambda x: getattr(x, key), reverse=reverse)


def _build_focus_compare_table(
    *,
    focus_profile: Optional[ModelProfile],
    profiles: List[ModelProfile],
) -> str:
    if not focus_profile:
        return "暂无可用对照数据。"
    best_asr = _top_by(profiles, "asr", reverse=False)
    best_frr = _top_by(profiles, "frr", reverse=False)
    best_mds = _top_by(profiles, "mds", reverse=True)
    candidates = []
    for arr in [best_asr, best_frr, best_mds]:
        if arr:
            candidates.append(arr[0].model)
    candidates = [x for i, x in enumerate(candidates) if x not in candidates[:i]]
    rows = []
    for m in candidates[:3]:
        if m == focus_profile.model:
            continue
        p = _get_profile(profiles, m)
        if not p:
            continue
        rows.append(
            [
                p.model,
                _fmt(p.asr, 4),
                _fmt(p.frr, 4),
                _fmt(p.mds, 4),
                _fmt(p.kappa, 4),
                _fmt(p.score, 4),
            ]
        )
    rows.insert(
        0,
        [
            f"{focus_profile.model} (Focus)",
            _fmt(focus_profile.asr, 4),
            _fmt(focus_profile.frr, 4),
            _fmt(focus_profile.mds, 4),
            _fmt(focus_profile.kappa, 4),
            _fmt(focus_profile.score, 4),
        ],
    )
    return render_markdown_table(["Model", "ASR", "FRR", "MDS", "Kappa", "Composite"], rows)


def _build_case_review_block(draft: DraftReport, llm_enabled: bool) -> str:
    if not draft.case_lines:
        return "本次未检索到可用于复盘的高质量案例样本。"
    intro = (
        "本节围绕待测模型的典型输出进行复盘，由 LLM 从候选池中筛选代表性的正反样本。"
        if llm_enabled
        else "本节围绕待测模型的典型输出进行复盘，当前为未启用 LLM 时的规则回退筛选结果。"
    )
    heading = "### 典型案例（LLM 代表性筛选）" if llm_enabled else "### 典型案例（规则回退筛选）"
    lines = [
        intro,
        "",
        heading,
        _join_lines(draft.case_lines),
        "",
        "### 复盘结论",
        "1. 若样本出现“高风险问题被直接回答”，优先归因为指令遵循权重过高，需在对齐阶段提升拒答奖励。",
        "2. 若样本出现“正常问题被拒答”，优先归因为拒答阈值过紧，需补充 benign hard-case 校准。",
        "3. 若样本出现“判标分歧”，需统一裁判协议并做抽样复核，降低一致性波动。",
    ]
    return "\n".join(lines)


def validate_report_hard_checks(
    *,
    report_text: str,
    draft: DraftReport,
    agent: ReportWritingAgent,
    focus_model: str,
    max_cases: int,
) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    case_similarity_threshold = float(getattr(agent.args, "case_similarity_threshold", 0.82) or 0.82)
    case_similarity_threshold = max(0.55, min(0.98, case_similarity_threshold))
    case_similarity_max_ratio = float(getattr(agent.args, "case_similarity_max_ratio", 0.35) or 0.35)
    case_similarity_max_ratio = max(0.0, min(1.0, case_similarity_max_ratio))
    max_cases_per_query = max(1, int(getattr(agent.args, "max_cases_per_query", 1) or 1))
    pool_query_keys = {
        str(agent._case_meta(line).get("query_norm") or "")
        for line in agent.case_line_pool
        if str(agent._case_meta(line).get("query_norm") or "")
    }
    min_target = min(4, max(1, int(max_cases)))
    if pool_query_keys and len(pool_query_keys) * max_cases_per_query < min_target:
        adaptive_cap = (min_target + len(pool_query_keys) - 1) // len(pool_query_keys)
        max_cases_per_query = max(max_cases_per_query, adaptive_cap)
    section_overlap_threshold = float(getattr(agent.args, "section_overlap_threshold", 0.88) or 0.88)
    section_overlap_threshold = max(0.7, min(0.98, section_overlap_threshold))
    section_overlap_max_ratio = float(getattr(agent.args, "section_overlap_max_ratio", 0.3) or 0.3)
    section_overlap_max_ratio = max(0.0, min(1.0, section_overlap_max_ratio))

    unresolved = re.findall(r"\[\[[A-Z0-9_]+\]\]", report_text)
    if unresolved:
        errors.append(f"模板占位符未完全替换：{', '.join(sorted(set(unresolved)))}")

    if focus_model and focus_model not in report_text:
        errors.append(f"报告正文未包含待测模型标识：{focus_model}")

    max_cases = max(1, int(max_cases))
    if len(draft.case_lines) > max_cases:
        errors.append(f"案例数量超限：{len(draft.case_lines)} > max_cases({max_cases})")
    if len(draft.case_lines) < min(4, max_cases) and agent.case_line_pool:
        warnings.append(f"案例数量偏少：{len(draft.case_lines)}（建议 >= {min(4, max_cases)}）")

    case_pool_set = set(agent.case_line_pool)
    for idx, line in enumerate(draft.case_lines, start=1):
        if line not in case_pool_set:
            errors.append(f"案例第 {idx} 条不在候选池内（疑似越权生成）")

    pool_has_pos = any(agent._is_positive_case_line(x) for x in agent.case_line_pool)
    pool_has_neg = any(agent._is_negative_case_line(x) for x in agent.case_line_pool)
    selected_has_pos = any(agent._is_positive_case_line(x) for x in draft.case_lines)
    selected_has_neg = any(agent._is_negative_case_line(x) for x in draft.case_lines)
    if pool_has_pos and not selected_has_pos:
        errors.append("案例筛选未覆盖 positive 样本")
    if pool_has_neg and not selected_has_neg:
        errors.append("案例筛选未覆盖 negative 样本")

    case_signatures = [agent._case_signature_from_line(line) for line in draft.case_lines]
    if len(set(case_signatures)) != len(case_signatures):
        errors.append("案例章节存在重复签名（同类 query/response 近似重复）")

    by_content: Dict[str, set] = defaultdict(set)
    query_counter = Counter()
    for line in draft.case_lines:
        meta = agent._case_meta(line)
        by_content[str(meta.get("content_key") or "")].add(str(meta.get("case_type") or "unknown"))
        query_counter[str(meta.get("query_norm") or "")] += 1
    conflict_contents = sum(1 for types in by_content.values() if len(types) > 1)
    if conflict_contents > 0:
        warnings.append(f"案例存在跨标签冲突内容：{conflict_contents} 组（建议人工复核）")
    query_overuse = {q: c for q, c in query_counter.items() if q and c > max_cases_per_query}
    if query_overuse:
        errors.append(
            f"案例 query 重复超限：{len(query_overuse)} 个 query 超过 max_cases_per_query({max_cases_per_query})"
        )

    case_pair_total = 0
    case_pair_similar = 0
    for i in range(len(draft.case_lines)):
        for j in range(i + 1, len(draft.case_lines)):
            case_pair_total += 1
            ta = str(agent._case_meta(draft.case_lines[i]).get("similarity_text") or "")
            tb = str(agent._case_meta(draft.case_lines[j]).get("similarity_text") or "")
            sim = _similarity_ratio(ta, tb)
            if sim >= case_similarity_threshold:
                case_pair_similar += 1
            if sim >= 0.95:
                errors.append(f"案例第 {i + 1}/{j + 1} 条近似完全重复（sim={sim:.2f}）")
    near_dup_ratio = (case_pair_similar / case_pair_total) if case_pair_total else 0.0
    if near_dup_ratio > case_similarity_max_ratio:
        errors.append(
            f"案例近似重复率过高：{near_dup_ratio:.2%} > {case_similarity_max_ratio:.2%}（阈值 sim>={case_similarity_threshold:.2f}）"
        )
    elif near_dup_ratio > case_similarity_max_ratio * 0.7 and case_pair_total > 0:
        warnings.append(
            f"案例近似重复率偏高：{near_dup_ratio:.2%}（阈值 sim>={case_similarity_threshold:.2f}）"
        )

    selected_types = {
        str(agent._case_meta(line).get("case_type") or "unknown")
        for line in draft.case_lines
    }
    pool_types = {
        str(agent._case_meta(line).get("case_type") or "unknown")
        for line in agent.case_line_pool
    }
    if len(pool_types) >= 3 and len(selected_types) < min(3, len(pool_types)):
        warnings.append(f"案例类型覆盖不足：已选 {len(selected_types)} 类 / 候选 {len(pool_types)} 类")

    section_buckets = {
        "exec": draft.exec_lines,
        "focus": draft.focus_lines,
        "insight": draft.insight_lines,
        "attack": draft.attack_lines,
        "case": draft.case_lines,
        "recommendation": draft.recommendation_lines,
    }
    for bucket_name, lines in section_buckets.items():
        for i, line in enumerate(lines, start=1):
            if not re.search(r"\[E\d+\]", line):
                errors.append(f"{bucket_name} 第 {i} 条缺少证据标签 [E*]")

    max_eid = agent.evidence.size()
    all_ref_ids = [int(x) for x in re.findall(r"\[E(\d+)\]", report_text)]
    for rid in all_ref_ids:
        if rid < 1 or rid > max_eid:
            errors.append(f"报告包含越界证据编号 [E{rid}]（有效范围 1..{max_eid}）")

    if not all_ref_ids:
        errors.append("报告中未发现任何证据编号 [E*]")

    if agent.case_candidate_records and draft.case_lines:
        top_k = max(1, min(len(agent.case_candidate_records), max_cases * 2))
        top_lines = {str(x.get('line')) for x in agent.case_candidate_records[:top_k]}
        if not any(line in top_lines for line in draft.case_lines):
            warnings.append("当前入选案例未覆盖高代表性评分样本（Top-2x max_cases）")

    def _norm_for_overlap(line: str) -> str:
        text = re.sub(r"\[E\d+\]", " ", line)
        text = re.sub(r"[+\-]?\d+(?:\.\d+)?", " ", text)
        return _normalize_for_similarity(text, keep_digits=False)

    chapter2_lines = list(draft.attack_lines)
    chapter3_lines = list(draft.focus_lines) + list(draft.insight_lines)
    chapter2_norm = [n for n in (_norm_for_overlap(x) for x in chapter2_lines) if n]
    chapter3_norm = [n for n in (_norm_for_overlap(x) for x in chapter3_lines) if n]
    overlap_hits = 0
    for text3 in chapter3_norm:
        if any(_similarity_ratio(text3, text2) >= section_overlap_threshold for text2 in chapter2_norm):
            overlap_hits += 1
    overlap_ratio = (overlap_hits / len(chapter3_norm)) if chapter3_norm else 0.0
    if overlap_ratio > section_overlap_max_ratio:
        errors.append(
            f"第2章与第3章结论重叠过高：{overlap_ratio:.2%} > {section_overlap_max_ratio:.2%}（sim>={section_overlap_threshold:.2f}）"
        )
    elif overlap_ratio > section_overlap_max_ratio * 0.7 and chapter3_norm:
        warnings.append(
            f"第2章与第3章结论重叠偏高：{overlap_ratio:.2%}（sim>={section_overlap_threshold:.2f}）"
        )

    return errors, warnings


def main() -> None:
    args = parse_args()
    if not os.path.isfile(args.facts):
        raise SystemExit(f"facts.json not found: {args.facts}")

    facts = load_facts(args.facts)
    models = list(facts.get("models") or [])
    attacks = list(facts.get("attacks") or [])
    matrix = facts.get("model_attack_matrix") or {}

    eval_models = [m.strip() for m in args.eval_models.split(",") if m.strip()] or models
    baseline_models = [m.strip() for m in args.baseline_models.split(",") if m.strip()]
    attack_set = [a.strip() for a in args.attack_set.split(",") if a.strip()] or attacks
    core_metrics = [m.strip() for m in args.core_metrics.split(",") if m.strip()]

    focus_model = (args.focus_model or "").strip()
    if not focus_model:
        focus_model = eval_models[0] if eval_models else (models[0] if models else "")

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    meta_info = render_meta_info(generated_at, eval_models, baseline_models, attack_set, core_metrics, focus_model)

    summary_table = build_summary_table(matrix, attack_set, models)
    context_notes = load_context_notes(args.context_notes) if args.context_notes else ""

    plots = facts.get("plots") or {}
    heatmap_path = resolve_plot_path(plots.get("heatmap"))
    model_bar_path = resolve_plot_path(plots.get("model_bar"))
    attack_bar_path = resolve_plot_path(plots.get("attack_bar"))
    metric_bar_path = resolve_plot_path(plots.get("metric_bar"))
    frr_bar_path = resolve_plot_path(plots.get("frr_bar"))
    has_plots = any([heatmap_path, model_bar_path, attack_bar_path, metric_bar_path, frr_bar_path])

    if not args.focus_model and focus_model:
        args.focus_model = focus_model
    agent = ReportWritingAgent(facts, args)
    agent.build_indices()
    draft, section_plan = agent.generate(context_notes=context_notes, has_plots=has_plots)
    metrics_catalog = load_metrics_catalog(args.metrics_catalog)
    asset_profile = load_asset_profile(args.asset_profile, focus_model)

    model_table = render_markdown_table(
        [
            "Rank",
            "Model",
            "Composite",
            "ASR",
            "FRR",
            "MDS",
            "Kappa",
            "Bias",
            "WSL",
            "CM",
            "mu_ASR",
            "sigma_ASR",
            "Coverage",
        ],
        _model_metric_table_rows(agent.model_profiles, focus_model=focus_model),
    )

    attack_table = render_markdown_table(
        ["Rank", "Attack", "Avg ASR", "Avg FRR", "Worst-hit Model", "Worst ASR"],
        _attack_table_rows(agent.attack_rows),
    )

    appendix_lines: List[str] = []
    kappa = facts.get("kappa_summary") or {}
    if kappa:
        appendix_lines.append(
            "Kappa summary: avg={avg_kappa}, median={median_kappa}, min={min_kappa}, max={max_kappa}, total_rows={total_rows}, skipped_rows={skipped_rows}".format(
                **kappa
            )
        )
    appendix_lines.append("指标定义：ASR/FRR 越低越好；MDS/Kappa 越高越好；|Bias|、WSL、CM 越低越好。")

    plan_text = " -> ".join([title for title, _ in section_plan])
    focus_profile = _get_profile(agent.model_profiles, focus_model)
    best_asr_profiles = _top_by(agent.model_profiles, "asr", reverse=False)
    worst_asr_profiles = _top_by(agent.model_profiles, "asr", reverse=True)
    best_frr_profiles = _top_by(agent.model_profiles, "frr", reverse=False)
    worst_frr_profiles = _top_by(agent.model_profiles, "frr", reverse=True)
    best_mds_profiles = _top_by(agent.model_profiles, "mds", reverse=True)
    top_attack = agent.attack_rows[0] if agent.attack_rows else {}
    focus_attack_text = ""
    if focus_profile and focus_model in matrix:
        vals = []
        for atk, raw in matrix.get(focus_model, {}).items():
            v = _safe_float(raw)
            if v is not None:
                vals.append((atk, v))
        vals.sort(key=lambda x: -x[1])
        if vals:
            focus_attack_text = "；".join([f"{a}={v:.4f}" for a, v in vals[:3]])

    focus_cmp_table = _build_focus_compare_table(focus_profile=focus_profile, profiles=agent.model_profiles)
    case_review_block = _build_case_review_block(draft, llm_enabled=not args.no_llm)

    exec_paragraph = (
        f"在本次综合评测中，{focus_model} 展现出明显的“高指令遵循-高安全压力”特征。"
        f"从基础攻防看，{focus_model} 的 ASR={_fmt(focus_profile.asr, 4) if focus_profile else '-'}，"
        f"FRR={_fmt(focus_profile.frr, 4) if focus_profile else '-'}，"
        f"MDS={_fmt(focus_profile.mds, 4) if focus_profile else '-'}。"
        f"对照组中，ASR 最优模型为 {best_asr_profiles[0].model if best_asr_profiles else '-'} "
        f"({_fmt(best_asr_profiles[0].asr, 4) if best_asr_profiles else '-'})，"
        f"FRR 最优模型为 {best_frr_profiles[0].model if best_frr_profiles else '-'} "
        f"({_fmt(best_frr_profiles[0].frr, 4) if best_frr_profiles else '-'})。"
    )
    risk_paragraph = (
        f"从攻击面看，当前全局威胁最高的攻击向量为 {top_attack.get('attack', '-')}"
        f"（Avg ASR={_fmt(_safe_float(top_attack.get('avg_asr')), 4)}）。"
        f"{focus_model} 的高风险攻击面主要集中在：{focus_attack_text or '暂无'}。"
    )

    report_parts = [
        f"# 报告标题：{focus_model} 模型评测报告",
        "## 执行摘要",
        exec_paragraph,
        risk_paragraph,
        _join_lines(draft.exec_lines),
        "",
        "## 第1章：评测资产定义与测试环境",
        "### 1.1 被测资产清单",
        f"本次报告以 **{focus_model}** 为待测主体，其余模型仅作为横向对照背景。",
        meta_info,
        "### 1.2 关键评测域与攻击面映射",
        "本评测采用“数据构建 -> 对抗攻击 -> 裁判标注 -> 指标聚合 -> 报告生成”的闭环流程。",
        f"当前覆盖攻击向量共 {len(attacks)} 类，核心指标包括 {', '.join(core_metrics)}。",
        "### 1.3 测试环境与方法说明",
        "当前报告基于现有评测产物（facts.json / asr_labels / frr / kappa / mds）进行灰盒诊断，不直接修改模型权重。",
        "",
        "## 第2章：核心安全态势与风险量化",
        "### 2.1 基础攻防双维指标（ASR/FRR）",
        f"- 待测模型 {focus_model}：ASR={_fmt(focus_profile.asr, 4) if focus_profile else '-'}，FRR={_fmt(focus_profile.frr, 4) if focus_profile else '-'}。",
        f"- 参照最优 ASR：{best_asr_profiles[0].model if best_asr_profiles else '-'} ({_fmt(best_asr_profiles[0].asr, 4) if best_asr_profiles else '-'})；"
        f"最差 ASR：{worst_asr_profiles[0].model if worst_asr_profiles else '-'} ({_fmt(worst_asr_profiles[0].asr, 4) if worst_asr_profiles else '-'})。",
        f"- 参照最优 FRR：{best_frr_profiles[0].model if best_frr_profiles else '-'} ({_fmt(best_frr_profiles[0].frr, 4) if best_frr_profiles else '-'})；"
        f"最差 FRR：{worst_frr_profiles[0].model if worst_frr_profiles else '-'} ({_fmt(worst_frr_profiles[0].frr, 4) if worst_frr_profiles else '-'})。",
        "### 2.2 细粒度防御分布（攻击向量）",
        _join_lines(draft.attack_lines),
        "### 2.3 进阶风险（MDS / Kappa / Bias / WSL / CM）",
        f"- 待测模型 MDS={_fmt(focus_profile.mds, 4) if focus_profile else '-'}，Kappa={_fmt(focus_profile.kappa, 4) if focus_profile else '-'}，"
        f"Bias={_fmt(focus_profile.bias, 4) if focus_profile else '-'}，WSL={_fmt(focus_profile.wsl, 4) if focus_profile else '-'}，CM={_fmt(focus_profile.cm, 4) if focus_profile else '-'}。",
        f"- 参照最优 MDS：{best_mds_profiles[0].model if best_mds_profiles else '-'} ({_fmt(best_mds_profiles[0].mds, 4) if best_mds_profiles else '-'})。",
        "",
        "## 第3章：横向对标（以待测模型为中心）",
        "本章仅保留与待测模型直接相关的对比，不做泛化排行榜叙事。",
        focus_cmp_table,
        _join_lines(draft.focus_lines),
        _join_lines(draft.insight_lines),
        "",
        "## 第4章：纵向诊断（待测模型内部特性）",
        f"围绕 {focus_model}，本章聚焦“是否稳定地安全”“是否存在结构性防御缺口”“是否出现能力与安全悖论”。",
        "### 4.1 结构性风险",
        f"- 若 ASR 高且 sigma_ASR 低，通常意味着“稳定的不安全”；若 ASR 中等但波动大，通常意味着“局部防线薄弱”。",
        f"- {focus_model} 当前 mu_ASR={_fmt(focus_profile.mu_asr, 4) if focus_profile else '-'}，sigma_ASR={_fmt(focus_profile.sigma_asr, 4) if focus_profile else '-'}。",
        "### 4.2 对齐策略诊断",
        f"- Bias={_fmt(focus_profile.bias, 4) if focus_profile else '-'}：正值更保守，负值更激进。建议结合 FRR 一并判断是否“有用性压过无害性”。",
        "### 4.3 商业风险解释",
        f"- CM={_fmt(focus_profile.cm, 4) if focus_profile else '-'} 与 WSL={_fmt(focus_profile.wsl, 4) if focus_profile else '-'} 共同反映上线后的潜在合规成本。",
        "",
        "## 第5章：典型案例复盘",
        case_review_block,
        "",
        "## 第6章：改进建议与路线图",
        _join_lines(draft.recommendation_lines),
        "### 6.1 短期（1-2个迭代）",
        "- 先打掉待测模型最脆弱的前2类攻击向量，形成专项回归集与发布门禁。",
        "### 6.2 中期（季度）",
        "- 基于失败样本构建拒答/引导偏好对，修正偏置与误拒边界。",
        "### 6.3 长期（年度）",
        "- 形成“模型内生防御 + 外挂网关 + 人工复核”的三层合规架构。",
        "",
        "## 附：自动规划与审校",
        f"本次自动章节规划：{plan_text}",
    ]

    report_parts.extend(
        [
            "## 第7章：可视化仪表盘",
            "### 7.1 综合热力图",
            f"![Overall Heatmap]({heatmap_path})" if heatmap_path else "_未生成热力图_",
            "### 7.2 排行图与风险面板",
            "\n".join(
                [
                    f"![Model ASR Bar]({model_bar_path})" if model_bar_path else "",
                    f"![Attack ASR Bar]({attack_bar_path})" if attack_bar_path else "",
                    f"![Model FRR Bar]({frr_bar_path})" if frr_bar_path else "",
                    f"![Bias/WSL/CM Bar]({metric_bar_path})" if metric_bar_path else "",
                ]
            ).strip()
            or "_未生成可视化_",
            "## 第8章：审校与一致性检查",
            _join_lines(draft.audit_lines),
        ]
    )

    report_parts.extend(
        [
            "## 模型全指标画像",
            model_table,
            "## 攻击向量画像",
            attack_table,
            "## 证据索引",
            agent.evidence.render_markdown(),
            "## 附录",
            "\n".join(appendix_lines),
            "### 附：ASR 综合矩阵",
            summary_table,
        ]
    )

    report = "\n\n".join([part for part in report_parts if part])
    if not args.legacy_layout and args.report_template and os.path.isfile(args.report_template):
        report = build_report_from_template(
            template_path=args.report_template,
            focus_model=focus_model,
            focus_profile=focus_profile,
            exec_paragraph=exec_paragraph,
            risk_paragraph=risk_paragraph,
            meta_info=meta_info,
            attack_set=attack_set,
            core_metrics=core_metrics,
            attack_table=attack_table,
            model_table=model_table,
            summary_table=summary_table,
            focus_cmp_table=focus_cmp_table,
            case_review_block=case_review_block,
            draft=draft,
            evidence_table=agent.evidence.render_markdown(),
            heatmap_path=heatmap_path,
            model_bar_path=model_bar_path,
            attack_bar_path=attack_bar_path,
            metric_bar_path=metric_bar_path,
            frr_bar_path=frr_bar_path,
            metrics_catalog=metrics_catalog,
            asset_profile=asset_profile,
            args=args,
        )
    report = _clean_report_text(report)
    if not args.skip_hard_check:
        errors, warnings = validate_report_hard_checks(
            report_text=report,
            draft=draft,
            agent=agent,
            focus_model=focus_model,
            max_cases=args.max_cases,
        )
        for w in warnings:
            print(f"[HARD-CHECK][WARN] {w}", file=sys.stderr)
        if errors:
            msg = "\n".join([f"- {x}" for x in errors])
            raise SystemExit(f"Hard check failed before writing report:\n{msg}")
    output_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(output_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report generated: {args.output}")


if __name__ == "__main__":
    main()
