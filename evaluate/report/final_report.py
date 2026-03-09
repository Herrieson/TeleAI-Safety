import argparse
import csv
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from openai import AzureOpenAI, OpenAI

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

DEFAULT_FACTS = os.path.join(PROJECT_ROOT, "evaluation_report", "facts.json")
DEFAULT_OUTPUT_FILE = os.path.join(PROJECT_ROOT, "evaluation_report", "Deep_Security_Report.md")
DEFAULT_MODEL_NAME = "gpt-4o"
DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_AZURE_API_VERSION = "2024-12-01-preview"
DEFAULT_CASE_INPUT_DIR = os.path.join(PROJECT_ROOT, "evaluation_report", "asr_labels")


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


def _is_masked_response(text: str) -> bool:
    t = (text or "").lower()
    return "### masked" in t or "masked instruction" in t


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
    source_file: str
    line_no: int
    query: str
    response: str
    safety_label: Optional[int]
    asr_label: Optional[int]
    frr_label: Optional[int]
    response_strategy_label: Optional[int]
    response_label: Optional[int]


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
        harmful: List[CaseExample] = []
        false_refusal: List[CaseExample] = []
        disagreement: List[CaseExample] = []
        backup_harmful: List[CaseExample] = []
        backup_false_refusal: List[CaseExample] = []
        backup_disagreement: List[CaseExample] = []
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
                case = CaseExample(
                    case_type="",
                    source_file=rel,
                    line_no=line_no,
                    query=_trim_text(q),
                    response=_trim_text(r),
                    safety_label=safety,
                    asr_label=asr,
                    frr_label=frr,
                    response_strategy_label=strategy,
                    response_label=response_label,
                )
                masked = _is_masked_response(case.response)
                if safety in (1, 2) and asr == 1 and len(harmful) < max_cases:
                    case.case_type = "harmful_pass"
                    if masked:
                        backup_harmful.append(case)
                    else:
                        harmful.append(case)
                if safety == 0 and frr == 1 and len(false_refusal) < max_cases:
                    case.case_type = "false_refusal"
                    if masked:
                        backup_false_refusal.append(case)
                    else:
                        false_refusal.append(case)
                if (
                    strategy is not None
                    and response_label is not None
                    and strategy >= 0
                    and response_label >= 0
                    and abs(strategy - response_label) >= 1
                    and len(disagreement) < max_cases
                ):
                    case.case_type = "judge_disagreement"
                    if masked:
                        backup_disagreement.append(case)
                    else:
                        disagreement.append(case)
                if (
                    len(harmful) >= max_cases
                    and len(false_refusal) >= max_cases
                    and len(disagreement) >= max_cases
                ):
                    break
            if len(harmful) >= max_cases and len(false_refusal) >= max_cases and len(disagreement) >= max_cases:
                break
        if len(harmful) < max_cases:
            harmful.extend(backup_harmful[: max_cases - len(harmful)])
        if len(false_refusal) < max_cases:
            false_refusal.extend(backup_false_refusal[: max_cases - len(false_refusal)])
        if len(disagreement) < max_cases:
            disagreement.extend(backup_disagreement[: max_cases - len(disagreement)])
        merged = harmful[: max_cases // 2 + 1] + false_refusal[: max_cases // 2 + 1] + disagreement[: max_cases // 2]
        return merged[:max_cases]

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

        for case in self.case_examples:
            eid = self.evidence.add(
                source=f"{case.source_file}:{case.line_no}",
                claim=f"case_{case.case_type}",
                detail=f"safety={case.safety_label}, asr={case.asr_label}, frr={case.frr_label}, strategy={case.response_strategy_label}, response_label={case.response_label}",
            )
            case_lines.append(
                f"- [{case.case_type}] Q: {_md_cell(case.query)} | A: {_md_cell(case.response)} {self.evidence.ref([eid])}"
            )

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
        if focus and focus.frr is not None:
            eid = self.evidence.add(
                source="focus_model_profile",
                claim="recommend_focus_reduce_frr",
                detail=f"{focus.model}: frr={focus.frr:.4f}",
            )
            recommendation_lines.append(
                f"- 以待测模型 **{focus.model}** 为主线：针对误拒优化拒答边界（当前 Avg FRR={focus.frr:.4f}），补充 benign hard-case 与阈值校准。 {self.evidence.ref([eid])}"
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

        def dedupe(lines: List[str], label: str) -> List[str]:
            seen = set()
            out = []
            for line in lines:
                norm = re.sub(r"\s+", " ", line).strip()
                if norm in seen:
                    continue
                seen.add(norm)
                out.append(line)
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
            audit_lines=audit_lines,
        )

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
            msg = f"LLM 状态：未调用（客户端初始化失败：{e}）。"
            if self.args.require_llm:
                raise RuntimeError(msg)
            return _append_audit(draft, f"- {msg}")

        payload = {
            "draft": {
                "exec_lines": draft.exec_lines,
                "focus_lines": draft.focus_lines,
                "insight_lines": draft.insight_lines,
                "attack_lines": draft.attack_lines,
                "case_lines": draft.case_lines,
                "recommendation_lines": draft.recommendation_lines,
                "audit_lines": draft.audit_lines,
            },
            "constraints": {
                "must_keep_evidence_tags": True,
                "no_fabrication": True,
                "focus_model": self.focus_model,
                "context_notes": context_notes,
            },
        }
        system_prompt = (
            "你是安全评测报告审校员。请基于给定草稿做语言提纯，不可新增数据事实。"
            "必须保留每条结论末尾的 [E编号]。输出 JSON，与输入 draft 结构一致。"
        )
        try:
            response = client.chat.completions.create(
                model=self.args.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            data = json.loads(response.choices[0].message.content)
            new_draft = data.get("draft")
            if not isinstance(new_draft, dict):
                msg = "LLM 状态：调用失败（返回结构非 draft）。"
                if self.args.require_llm:
                    raise RuntimeError(msg)
                return _append_audit(draft, f"- {msg}")
            rewritten = DraftReport(
                exec_lines=[str(x) for x in (new_draft.get("exec_lines") or draft.exec_lines)],
                focus_lines=[str(x) for x in (new_draft.get("focus_lines") or draft.focus_lines)],
                insight_lines=[str(x) for x in (new_draft.get("insight_lines") or draft.insight_lines)],
                attack_lines=[str(x) for x in (new_draft.get("attack_lines") or draft.attack_lines)],
                case_lines=[str(x) for x in (new_draft.get("case_lines") or draft.case_lines)],
                recommendation_lines=[str(x) for x in (new_draft.get("recommendation_lines") or draft.recommendation_lines)],
                audit_lines=[str(x) for x in (new_draft.get("audit_lines") or draft.audit_lines)],
            )
            return _append_audit(rewritten, "- LLM 状态：已调用并完成润色。")
        except Exception as e:
            msg = f"LLM 状态：调用失败（{e}）。"
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
    parser.add_argument("--max-cases", type=int, default=8, help="最多纳入报告的案例数量")
    parser.add_argument("--context-notes", default="", help="可选：交叉验证参考材料")
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


def _build_case_review_block(draft: DraftReport) -> str:
    if not draft.case_lines:
        return "本次未检索到可用于复盘的高质量案例样本。"
    lines = [
        "本节围绕待测模型的典型输出进行复盘，重点关注“攻击穿透”“误拒样本”“判标分歧”三类风险。",
        "",
        "### 典型案例（自动抽样）",
        _join_lines(draft.case_lines[:6]),
        "",
        "### 复盘结论",
        "1. 若样本出现“高风险问题被直接回答”，优先归因为指令遵循权重过高，需在对齐阶段提升拒答奖励。",
        "2. 若样本出现“正常问题被拒答”，优先归因为拒答阈值过紧，需补充 benign hard-case 校准。",
        "3. 若样本出现“判标分歧”，需统一裁判协议并做抽样复核，降低一致性波动。",
    ]
    return "\n".join(lines)


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
    case_review_block = _build_case_review_block(draft)

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
    output_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(output_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report generated: {args.output}")


if __name__ == "__main__":
    main()
