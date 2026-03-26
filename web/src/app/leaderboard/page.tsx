"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatedNumber } from "@/components/common/AnimatedNumber";
import { useI18n } from "@/components/common/LocaleProvider";
import { ApiError, getLeaderboard } from "@/lib/api";
import { formatDateTime } from "@/lib/i18n";
import type { LeaderboardMetric, LeaderboardMetricBetter, LeaderboardResponse, LeaderboardRow } from "@/lib/types";

const POLL_INTERVAL_MS = 15000;

type RankMap = Map<string, number>;

function normalizeMetricValue(value: number | null | undefined, better: LeaderboardMetricBetter): number | null {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return null;
  }
  if (better === "absolute_zero") {
    return Math.abs(value);
  }
  return value;
}

function recommendedAscending(better: LeaderboardMetricBetter): boolean {
  return better === "lower" || better === "absolute_zero";
}

function compareNullableNumber(left: number | null, right: number | null, ascending: boolean): number {
  if (left === null && right === null) {
    return 0;
  }
  if (left === null) {
    return 1;
  }
  if (right === null) {
    return -1;
  }
  if (left === right) {
    return 0;
  }
  return ascending ? left - right : right - left;
}

function buildRankMap(rows: LeaderboardRow[], metric: LeaderboardMetric, ascending: boolean): RankMap {
  const sorted = [...rows].sort((left, right) => {
    const leftValue = normalizeMetricValue(left.metrics[metric.key], metric.better);
    const rightValue = normalizeMetricValue(right.metrics[metric.key], metric.better);
    const diff = compareNullableNumber(leftValue, rightValue, ascending);
    if (diff !== 0) {
      return diff;
    }
    return left.model.localeCompare(right.model);
  });

  const rankMap: RankMap = new Map();
  let currentRank = 0;
  let previousValue: number | null = null;

  sorted.forEach((row, index) => {
    const value = normalizeMetricValue(row.metrics[metric.key], metric.better);
    if (value !== previousValue) {
      currentRank = index + 1;
      previousValue = value;
    }
    rankMap.set(row.model, value === null ? 0 : currentRank);
  });

  return rankMap;
}

function metricLabel(metric: LeaderboardMetric, locale: "zh" | "en"): string {
  const zhMap: Record<string, string> = {
    avg_asr: "平均 ASR",
    avg_frr: "平均 FRR",
    mu_asr: "mu ASR",
    sigma_asr: "sigma ASR",
    mds: "MDS",
    bias: "Bias",
    wsl: "WSL",
    cm: "CM",
    avg_kappa: "平均 Kappa",
    median_kappa: "中位 Kappa",
    min_kappa: "最小 Kappa",
    max_kappa: "最大 Kappa"
  };
  if (locale === "zh") {
    return zhMap[metric.key] || metric.label;
  }
  return metric.label;
}

function metricDirectionText(metric: LeaderboardMetric, locale: "zh" | "en"): string {
  if (metric.better === "higher") {
    return locale === "zh" ? "高优先" : "Higher Better";
  }
  if (metric.better === "absolute_zero") {
    return locale === "zh" ? "越接近 0 越优" : "Closer to 0 Better";
  }
  return locale === "zh" ? "低优先" : "Lower Better";
}

function formatMetricValue(value: number | null | undefined, metric: LeaderboardMetric, locale: "zh" | "en"): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  const localeTag = locale === "zh" ? "zh-CN" : "en-US";
  if (metric.format === "percent") {
    return `${(value * 100).toLocaleString(localeTag, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    })}%`;
  }
  return value.toLocaleString(localeTag, {
    minimumFractionDigits: 0,
    maximumFractionDigits: Math.max(2, metric.precision)
  });
}

export default function LeaderboardPage() {
  const { locale } = useI18n();
  const text =
    locale === "zh"
      ? {
          title: "模型指标排行榜",
          subtitle: "基于 evaluate/evaluation_report/all_metrics_summary.csv 的模型对比视图。",
          monitor: "排行榜",
          metric: "排序指标",
          reverseOrder: "反向排序",
          standardOrder: "标准排序",
          refresh: "刷新",
          refreshing: "刷新中...",
          loading: "正在加载排行榜...",
          noData: "暂无可展示的模型评估数据。",
          source: "数据源",
          sourceUpdated: "数据更新时间",
          lastUpdated: "页面更新时间",
          modelCount: "模型数",
          metricCount: "指标数",
          selectedRank: "当前指标排名",
          model: "模型",
          rowsHint: (count: number) => `共 ${count} 个模型，所有指标列均展示名次与数值。`,
          direction: "推荐规则",
          sync: "同步中..."
        }
      : {
          title: "Model Leaderboard",
          subtitle: "Model comparison from evaluate/evaluation_report/all_metrics_summary.csv.",
          monitor: "Leaderboard",
          metric: "Sort Metric",
          reverseOrder: "Reverse",
          standardOrder: "Standard",
          refresh: "Refresh",
          refreshing: "Refreshing...",
          loading: "Loading leaderboard...",
          noData: "No model metrics available.",
          source: "Source",
          sourceUpdated: "Source Updated",
          lastUpdated: "Page Updated",
          modelCount: "Models",
          metricCount: "Metrics",
          selectedRank: "Selected Rank",
          model: "Model",
          rowsHint: (count: number) => `${count} models, each metric column shows rank and value.`,
          direction: "Recommended Rule",
          sync: "syncing..."
        };

  const [payload, setPayload] = useState<LeaderboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [selectedMetricKey, setSelectedMetricKey] = useState("");
  const [reverseOrder, setReverseOrder] = useState(false);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | null>(null);
  const loadingRef = useRef(false);

  const loadLeaderboard = useCallback(async (background = false) => {
    if (loadingRef.current) {
      return;
    }
    loadingRef.current = true;
    if (background) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    try {
      const data = await getLeaderboard();
      setPayload(data);
      setLastUpdatedAt(Date.now());
      setError("");
    } catch (err) {
      const message = err instanceof ApiError ? err.message : String(err);
      setError(message);
    } finally {
      setLoading(false);
      setRefreshing(false);
      loadingRef.current = false;
    }
  }, []);

  useEffect(() => {
    void loadLeaderboard(false);
  }, [loadLeaderboard]);

  useEffect(() => {
    const timer = setInterval(() => {
      void loadLeaderboard(true);
    }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [loadLeaderboard]);

  useEffect(() => {
    if (!payload || payload.metrics.length === 0) {
      setSelectedMetricKey("");
      return;
    }
    const hasCurrent = payload.metrics.some((metric) => metric.key === selectedMetricKey);
    if (!hasCurrent) {
      setSelectedMetricKey(payload.metrics[0].key);
      setReverseOrder(false);
    }
  }, [payload, selectedMetricKey]);

  const selectedMetric = useMemo(() => {
    if (!payload) {
      return null;
    }
    return payload.metrics.find((metric) => metric.key === selectedMetricKey) || payload.metrics[0] || null;
  }, [payload, selectedMetricKey]);

  const rankMapsByMetric = useMemo(() => {
    const maps = new Map<string, RankMap>();
    if (!payload) {
      return maps;
    }
    payload.metrics.forEach((metric) => {
      maps.set(metric.key, buildRankMap(payload.rows, metric, recommendedAscending(metric.better)));
    });
    return maps;
  }, [payload]);

  const selectedRankMap = useMemo(() => {
    if (!payload || !selectedMetric) {
      return new Map<string, number>();
    }
    const ascending = reverseOrder ? !recommendedAscending(selectedMetric.better) : recommendedAscending(selectedMetric.better);
    return buildRankMap(payload.rows, selectedMetric, ascending);
  }, [payload, selectedMetric, reverseOrder]);

  const sortedRows = useMemo(() => {
    if (!payload || !selectedMetric) {
      return [];
    }
    const ascending = reverseOrder ? !recommendedAscending(selectedMetric.better) : recommendedAscending(selectedMetric.better);
    return [...payload.rows].sort((left, right) => {
      const leftValue = normalizeMetricValue(left.metrics[selectedMetric.key], selectedMetric.better);
      const rightValue = normalizeMetricValue(right.metrics[selectedMetric.key], selectedMetric.better);
      const diff = compareNullableNumber(leftValue, rightValue, ascending);
      if (diff !== 0) {
        return diff;
      }
      return left.model.localeCompare(right.model);
    });
  }, [payload, selectedMetric, reverseOrder]);

  return (
    <section aria-busy={loading || refreshing} className="panel p-5">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="label">{text.monitor}</p>
          <h2 className="title-gradient font-headline text-2xl font-semibold">{text.title}</h2>
          <p className="mt-1 text-sm text-slate-600">{text.subtitle}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="label" htmlFor="leaderboardMetric">
            {text.metric}
          </label>
          <select
            className="select w-full min-w-[180px] sm:w-[220px]"
            id="leaderboardMetric"
            onChange={(event) => {
              setSelectedMetricKey(event.target.value);
              setReverseOrder(false);
            }}
            value={selectedMetric?.key || ""}
          >
            {(payload?.metrics || []).map((metric) => (
              <option key={metric.key} value={metric.key}>
                {metricLabel(metric, locale)}
              </option>
            ))}
          </select>
          <button className="btn" onClick={() => setReverseOrder((prev) => !prev)} type="button">
            {reverseOrder ? text.standardOrder : text.reverseOrder}
          </button>
          <button className={refreshing ? "btn btn-busy" : "btn"} disabled={refreshing} onClick={() => void loadLeaderboard(true)} type="button">
            {refreshing ? text.refreshing : text.refresh}
          </button>
        </div>
      </div>

      <div className="stat-grid reveal-grid mb-5">
        <article className="stat-card">
          <p className="label mb-2">{text.modelCount}</p>
          <p className="stat-value">
            <AnimatedNumber value={payload?.model_count || 0} />
          </p>
        </article>
        <article className="stat-card">
          <p className="label mb-2">{text.metricCount}</p>
          <p className="stat-value">
            <AnimatedNumber value={payload?.metric_count || 0} />
          </p>
        </article>
      </div>

      <div className="mb-4 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-600">
        <div className="space-y-1">
          <p>
            {text.source}: <span className="mono">{payload?.source_csv || "-"}</span>
          </p>
          <p>
            {text.sourceUpdated}: {payload?.source_updated_at ? formatDateTime(payload.source_updated_at, locale) : "-"}
          </p>
          <p>
            {text.lastUpdated}: {lastUpdatedAt ? formatDateTime(lastUpdatedAt, locale) : "-"}
          </p>
        </div>
        {refreshing ? (
          <p aria-live="polite" className="inline-flex items-center gap-2 text-xs text-emerald-700">
            <span className="refresh-dot" />
            {text.sync}
          </p>
        ) : null}
      </div>

      {selectedMetric ? (
        <p className="notice mb-4 text-xs text-slate-500">
          {text.direction}: {metricDirectionText(selectedMetric, locale)}
          <span className="mx-2">|</span>
          {text.rowsHint(payload?.rows.length || 0)}
        </p>
      ) : null}

      {error ? (
        <p aria-live="assertive" className="notice notice-error mb-4" role="alert">
          {error}
        </p>
      ) : null}

      {loading ? (
        <p className="text-sm text-slate-600">{text.loading}</p>
      ) : !payload || !selectedMetric || payload.rows.length === 0 ? (
        <p className="notice p-4 text-sm text-slate-600">{text.noData}</p>
      ) : (
        <div className="data-table-wrap">
          <table className="data-table min-w-[1320px] bg-transparent">
            <thead>
              <tr>
                <th className="font-semibold">{text.selectedRank}</th>
                <th className="font-semibold">{text.model}</th>
                {payload.metrics.map((metric) => (
                  <th className="font-semibold" key={metric.key}>
                    <div className="flex flex-col gap-1">
                      <span>{metricLabel(metric, locale)}</span>
                      <span className="mono text-[10px] text-slate-500">{metricDirectionText(metric, locale)}</span>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sortedRows.map((row) => {
                const currentRank = selectedRankMap.get(row.model) || 0;
                return (
                  <tr className="align-top text-sm transition-colors" key={row.model}>
                    <td>
                      <span className="mode-chip mode-chip-full">{currentRank > 0 ? `#${currentRank}` : "-"}</span>
                    </td>
                    <td>
                      <p className="font-headline font-semibold text-slate-900">{row.model}</p>
                    </td>
                    {payload.metrics.map((metric) => {
                      const rankMap = rankMapsByMetric.get(metric.key);
                      const rank = rankMap?.get(row.model) || 0;
                      return (
                        <td key={`${row.model}:${metric.key}`}>
                          <div className="flex items-center gap-2">
                            <span className="mode-chip mode-chip-attack">{rank > 0 ? `#${rank}` : "-"}</span>
                            <span className="mono text-xs text-slate-700">{formatMetricValue(row.metrics[metric.key], metric, locale)}</span>
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
