"use client";

import { AnimatedNumber } from "@/components/common/AnimatedNumber";
import { useI18n } from "@/components/common/LocaleProvider";

type MetricCardsProps = {
  summary: Record<string, unknown>;
  emptyMessage?: string;
};

const primaryMetricOrder = [
  "asr_strict_avg",
  "asr_effective_avg",
  "frr_avg",
  "frr_effective_avg",
  "asr_avg"
];

const secondaryMetricOrder = [
  "mds_avg",
  "bias_avg",
  "wsl_avg",
  "cm_avg",
  "avg_kappa",
];

const countMetricOrder = ["total_samples", "attack_success_samples", "skipped_samples", "task_count", "scorer_count"];

const zhMetricLabelMap: Record<string, string> = {
  asr_avg: "ASR 平均值（Legacy）",
  asr_strict_avg: "ASR 严格平均值",
  asr_effective_avg: "ASR 有效平均值",
  frr_avg: "FRR 平均值",
  frr_effective_avg: "FRR 有效平均值",
  frr_invalid_rate_avg: "FRR 无效输出率",
  mds_avg: "MDS 平均值",
  bias_avg: "Bias 平均值",
  wsl_avg: "WSL 平均值",
  cm_avg: "CM 平均值",
  avg_kappa: "Kappa 平均值",
  task_count: "评估任务数",
  scorer_count: "评分器数量",
  total_samples: "总样本数",
  attack_success_samples: "攻击成功样本",
  skipped_samples: "跳过样本",
  scorers: "评分器"
};

const enMetricLabelMap: Record<string, string> = {
  asr_avg: "ASR Avg (Legacy)",
  asr_strict_avg: "ASR Strict Avg",
  asr_effective_avg: "ASR Effective Avg",
  frr_avg: "FRR Avg",
  frr_effective_avg: "FRR Effective Avg",
  frr_invalid_rate_avg: "FRR Invalid Rate Avg",
  mds_avg: "MDS Avg",
  bias_avg: "Bias Avg",
  wsl_avg: "WSL Avg",
  cm_avg: "CM Avg",
  avg_kappa: "Kappa Avg",
  task_count: "Task Count",
  scorer_count: "Scorer Count",
  total_samples: "Total Samples",
  attack_success_samples: "Attack Success Samples",
  skipped_samples: "Skipped Samples",
  scorers: "Scorers"
};

function labelForKey(key: string, locale: "zh" | "en"): string {
  const map = locale === "zh" ? zhMetricLabelMap : enMetricLabelMap;
  if (map[key]) {
    return map[key];
  }
  return key.replace(/_/g, " ");
}

function isPercentMetric(key: string): boolean {
  return /(asr|frr|_rate$|_ratio$)/i.test(key);
}

function isCountMetric(key: string): boolean {
  return /(count|rows|samples|total|skipped|success)/i.test(key);
}

function compactCountLabel(key: string, locale: "zh" | "en"): string {
  if (locale === "zh") {
    const zhMap: Record<string, string> = {
      task_count: "任务",
      scorer_count: "评分器",
      total_samples: "样本",
      attack_success_samples: "成功",
      skipped_samples: "跳过"
    };
    return zhMap[key] || labelForKey(key, locale);
  }
  const enMap: Record<string, string> = {
    task_count: "Tasks",
    scorer_count: "Scorers",
    total_samples: "Samples",
    attack_success_samples: "Success",
    skipped_samples: "Skipped"
  };
  return enMap[key] || labelForKey(key, locale);
}

function displayValue(
  key: string,
  value: number,
  locale: "zh" | "en"
): { shown: number; decimals: number; suffix: string; text: string } {
  const localeTag = locale === "zh" ? "zh-CN" : "en-US";
  if (isCountMetric(key)) {
    return {
      shown: value,
      decimals: 0,
      suffix: "",
      text: value.toLocaleString(localeTag, { maximumFractionDigits: 0 })
    };
  }
  if (isPercentMetric(key)) {
    const shown = value * 100;
    return {
      shown,
      decimals: 2,
      suffix: "%",
      text: shown.toLocaleString(localeTag, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      })
    };
  }
  return {
    shown: value,
    decimals: 4,
    suffix: "",
    text: value.toLocaleString(localeTag, {
      minimumFractionDigits: 4,
      maximumFractionDigits: 4
    })
  };
}

export function MetricCards({ summary, emptyMessage }: MetricCardsProps) {
  const { locale } = useI18n();
  const text =
    locale === "zh"
      ? {
          empty: "暂无指标汇总。",
          keyMetrics: "重点指标",
          supplement: "补充指标",
          scorers: "评分器",
          notGenerated: "未生成",
          na: "N/A"
        }
      : {
          empty: "No metric summary generated yet.",
          keyMetrics: "Key Metrics",
          supplement: "Supplementary",
          scorers: "Scorers",
          notGenerated: "Not generated",
          na: "N/A"
        };

  if (!summary || Object.keys(summary).length === 0) {
    return <p className="notice text-slate-600">{emptyMessage || text.empty}</p>;
  }

  const numericMap = new Map(
    Object.entries(summary).filter((entry): entry is [string, number] => typeof entry[1] === "number" && Number.isFinite(entry[1]))
  );
  const frrUnavailable = summary.frr_denominator_zero === true;

  const primaryMetrics = primaryMetricOrder
    .map((key) => {
      const unavailable = frrUnavailable && key.includes("frr");
      return { key, value: unavailable ? undefined : numericMap.get(key), unavailable };
    })
    .filter((item) => item.unavailable || typeof item.value === "number")
    .slice(0, 4);

  const secondaryMetrics = secondaryMetricOrder
    .map((key) => {
      const unavailable = frrUnavailable && key.includes("frr");
      return { key, value: unavailable ? undefined : numericMap.get(key), unavailable };
    })
    .filter((item) => item.unavailable || typeof item.value === "number")
    .concat(
      primaryMetricOrder
        .slice(4)
        .map((key) => {
          const unavailable = frrUnavailable && key.includes("frr");
          return { key, value: unavailable ? undefined : numericMap.get(key), unavailable };
        })
        .filter((item) => item.unavailable || typeof item.value === "number")
    );

  const compactCounts = countMetricOrder
    .map((key) => ({ key, value: numericMap.get(key) }))
    .filter((item): item is { key: string; value: number } => typeof item.value === "number");

  const scorersText = Array.isArray(summary.scorers) ? summary.scorers.join(", ") : "";

  return (
    <div className="space-y-3">
      <p className="label">{text.keyMetrics}</p>
      <div className="metric-hero-grid reveal-grid">
        {primaryMetrics.map(({ key, value, unavailable }) => {
          const formatted = typeof value === "number" ? displayValue(key, value, locale) : null;
          const accentClass = key.includes("effective")
            ? "metric-hero-card metric-hero-card-good"
            : key.includes("frr")
              ? "metric-hero-card metric-hero-card-warn"
              : "metric-hero-card";
          return (
            <article className={accentClass} key={key}>
              <p className="label mb-1">{labelForKey(key, locale)}</p>
              <p className="font-headline text-2xl font-semibold text-[#e4f2ff]">
                {unavailable || !formatted ? (
                  text.na
                ) : (
                  <AnimatedNumber decimals={formatted.decimals} suffix={formatted.suffix} value={formatted.shown} />
                )}
              </p>
            </article>
          );
        })}

        {!primaryMetrics.length ? (
          <article className="stat-card md:col-span-3">
            <p className="text-sm text-slate-600">{text.notGenerated}</p>
          </article>
        ) : null}
      </div>

      <article className="metric-summary-card">
        <div className="metric-summary-row">
          <span className="label">{text.scorers}</span>
          <span className="mono text-sm text-slate-700">{scorersText || "-"}</span>
        </div>

        {compactCounts.length ? (
          <div className="metric-chip-row mt-2">
            {compactCounts.map(({ key, value }) => (
              <span className="metric-chip" key={key}>
                {compactCountLabel(key, locale)} {displayValue(key, value, locale).text}
              </span>
            ))}
          </div>
        ) : null}

        {secondaryMetrics.length ? (
          <>
            <p className="label mt-3">{text.supplement}</p>
            <div className="metric-chip-row mt-2">
              {secondaryMetrics.map(({ key, value, unavailable }) => {
                const formatted = typeof value === "number" ? displayValue(key, value, locale) : null;
                const textValue = unavailable || !formatted ? text.na : `${formatted.text}${formatted.suffix}`;
                return (
                  <span className="metric-chip metric-chip-subtle" key={key}>
                    {labelForKey(key, locale)} {textValue}
                  </span>
                );
              })}
            </div>
          </>
        ) : null}
      </article>
    </div>
  );
}
