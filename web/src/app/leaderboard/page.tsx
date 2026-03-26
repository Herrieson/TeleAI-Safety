"use client";

import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatedNumber } from "@/components/common/AnimatedNumber";
import { useI18n } from "@/components/common/LocaleProvider";
import { ApiError, getLeaderboard } from "@/lib/api";
import { formatDateTime } from "@/lib/i18n";
import type { LeaderboardMetric, LeaderboardMetricBetter, LeaderboardResponse, LeaderboardRow } from "@/lib/types";

const POLL_INTERVAL_MS = 15000;

const CLOSED_SOURCE_MODELS = new Set(["gpt-5.4", "gpt-4o", "gpt-5", "gpt-5.2", "grok-4.1", "gemini-3.1-pro"]);

type RankMap = Map<string, number>;
type ModelSourceType = "open" | "closed";
type SourceFilter = "all" | ModelSourceType;

type SourceCounts = {
  all: number;
  open: number;
  closed: number;
};

function resolveModelSourceType(model: string): ModelSourceType {
  if (CLOSED_SOURCE_MODELS.has((model || "").trim())) {
    return "closed";
  }
  return "open";
}

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
    asr: "ASR",
    frr: "FRR",
    mds: "MDS",
    bias: "Bias",
    wsl: "WSL",
    cm: "CM",
    code_ability: "代码能力",
    hallucination: "幻觉"
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

function formatPercentValue(value: number | null | undefined, locale: "zh" | "en"): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  const localeTag = locale === "zh" ? "zh-CN" : "en-US";
  return `${(value * 100).toLocaleString(localeTag, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })}%`;
}

function rankChipClass(rank: number): string {
  if (rank === 1) {
    return "leaderboard-rank-chip leaderboard-rank-chip-top1";
  }
  if (rank === 2) {
    return "leaderboard-rank-chip leaderboard-rank-chip-top2";
  }
  if (rank === 3) {
    return "leaderboard-rank-chip leaderboard-rank-chip-top3";
  }
  return "leaderboard-rank-chip";
}

export default function LeaderboardPage() {
  const { locale } = useI18n();
  const text =
    locale === "zh"
      ? {
          title: "模型指标排行榜",
          subtitle: "基于 evaluate/evaluation_report 与 benchmark/result 的模型对比视图。",
          monitor: "排行榜",
          metric: "排序指标",
          reverseOrder: "反向排序",
          standardOrder: "标准排序",
          refresh: "刷新",
          refreshing: "刷新中...",
          loading: "正在加载排行榜...",
          noData: "暂无可展示的模型评估数据。",
          noRowsInFilter: "当前筛选下暂无模型。",
          source: "数据源",
          sourceUpdated: "数据更新时间",
          lastUpdated: "页面更新时间",
          modelCount: "模型数",
          metricCount: "指标数",
          selectedRank: "当前指标排名",
          model: "模型",
          sourceType: "模型类型",
          rowsHint: (count: number) => `当前显示 ${count} 个模型，指标列展示名次与数值。`,
          direction: "推荐规则",
          sync: "同步中...",
          viewAsrDetail: "查看细项",
          hideAsrDetail: "收起细项",
          asrDetailTitle: (model: string) => `${model} ASR 细项`,
          asrEffective: "ASR_effective",
          asrStrict: "ASR_strict",
          asrLegacy: "ASR_legacy",
          openSourceLabel: "开源",
          closedSourceLabel: "闭源",
          filterAll: "全部",
          filterOpen: "开源",
          filterClosed: "闭源",
          toggleFilterOpen: "点击展开筛选",
          toggleFilterClose: "点击收起筛选"
        }
      : {
          title: "Model Leaderboard",
          subtitle: "Model comparison from evaluate/evaluation_report and benchmark/result.",
          monitor: "Leaderboard",
          metric: "Sort Metric",
          reverseOrder: "Reverse",
          standardOrder: "Standard",
          refresh: "Refresh",
          refreshing: "Refreshing...",
          loading: "Loading leaderboard...",
          noData: "No model metrics available.",
          noRowsInFilter: "No model matched the selected filter.",
          source: "Source",
          sourceUpdated: "Source Updated",
          lastUpdated: "Page Updated",
          modelCount: "Models",
          metricCount: "Metrics",
          selectedRank: "Selected Rank",
          model: "Model",
          sourceType: "Source",
          rowsHint: (count: number) => `${count} model(s) shown, each metric column includes rank and value.`,
          direction: "Recommended Rule",
          sync: "syncing...",
          viewAsrDetail: "View Detail",
          hideAsrDetail: "Hide Detail",
          asrDetailTitle: (model: string) => `${model} ASR Breakdown`,
          asrEffective: "ASR_effective",
          asrStrict: "ASR_strict",
          asrLegacy: "ASR_legacy",
          openSourceLabel: "Open-source",
          closedSourceLabel: "Closed-source",
          filterAll: "All",
          filterOpen: "Open-source",
          filterClosed: "Closed-source",
          toggleFilterOpen: "Click to expand filters",
          toggleFilterClose: "Click to collapse filters"
        };

  const [payload, setPayload] = useState<LeaderboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [selectedMetricKey, setSelectedMetricKey] = useState("");
  const [reverseOrder, setReverseOrder] = useState(false);
  const [expandedAsrModel, setExpandedAsrModel] = useState("");
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("all");
  const [sourceFilterPanelOpen, setSourceFilterPanelOpen] = useState(false);
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

  const sourceCounts = useMemo<SourceCounts>(() => {
    const rows = payload?.rows || [];
    let open = 0;
    let closed = 0;
    rows.forEach((row) => {
      if (resolveModelSourceType(row.model) === "closed") {
        closed += 1;
      } else {
        open += 1;
      }
    });
    return {
      all: rows.length,
      open,
      closed
    };
  }, [payload]);

  const sourceFilteredRows = useMemo(() => {
    if (!payload) {
      return [] as LeaderboardRow[];
    }
    if (sourceFilter === "all") {
      return payload.rows;
    }
    return payload.rows.filter((row) => resolveModelSourceType(row.model) === sourceFilter);
  }, [payload, sourceFilter]);

  useEffect(() => {
    if (!expandedAsrModel) {
      return;
    }
    const exists = sourceFilteredRows.some((row) => row.model === expandedAsrModel);
    if (!exists) {
      setExpandedAsrModel("");
    }
  }, [sourceFilteredRows, expandedAsrModel]);

  const rankMapsByMetric = useMemo(() => {
    const maps = new Map<string, RankMap>();
    if (!payload) {
      return maps;
    }
    payload.metrics.forEach((metric) => {
      maps.set(metric.key, buildRankMap(sourceFilteredRows, metric, recommendedAscending(metric.better)));
    });
    return maps;
  }, [payload, sourceFilteredRows]);

  const selectedRankMap = useMemo(() => {
    if (!selectedMetric) {
      return new Map<string, number>();
    }
    const ascending = reverseOrder ? !recommendedAscending(selectedMetric.better) : recommendedAscending(selectedMetric.better);
    return buildRankMap(sourceFilteredRows, selectedMetric, ascending);
  }, [selectedMetric, reverseOrder, sourceFilteredRows]);

  const sortedRows = useMemo(() => {
    if (!selectedMetric) {
      return [] as LeaderboardRow[];
    }
    const ascending = reverseOrder ? !recommendedAscending(selectedMetric.better) : recommendedAscending(selectedMetric.better);
    return [...sourceFilteredRows].sort((left, right) => {
      const leftValue = normalizeMetricValue(left.metrics[selectedMetric.key], selectedMetric.better);
      const rightValue = normalizeMetricValue(right.metrics[selectedMetric.key], selectedMetric.better);
      const diff = compareNullableNumber(leftValue, rightValue, ascending);
      if (diff !== 0) {
        return diff;
      }
      return left.model.localeCompare(right.model);
    });
  }, [selectedMetric, reverseOrder, sourceFilteredRows]);

  const sourceFilterOptions = useMemo(
    () => [
      { value: "all" as const, label: text.filterAll, count: sourceCounts.all },
      { value: "open" as const, label: text.filterOpen, count: sourceCounts.open },
      { value: "closed" as const, label: text.filterClosed, count: sourceCounts.closed }
    ],
    [text, sourceCounts]
  );

  return (
    <section aria-busy={loading || refreshing} className="panel leaderboard-panel p-5">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="label">{text.monitor}</p>
          <h2 className="title-gradient font-headline text-2xl font-semibold">{text.title}</h2>
          <p className="mt-1 text-sm text-slate-500">{text.subtitle}</p>
        </div>
        <div className="leaderboard-toolbar flex flex-wrap items-center gap-2">
          <label className="label" htmlFor="leaderboardMetric">
            {text.metric}
          </label>
          <select
            className="select w-full min-w-[180px] sm:w-[220px]"
            id="leaderboardMetric"
            onChange={(event) => {
              setSelectedMetricKey(event.target.value);
              setReverseOrder(false);
              setExpandedAsrModel("");
            }}
            value={selectedMetric?.key || ""}
          >
            {(payload?.metrics || []).map((metric) => (
              <option key={metric.key} value={metric.key}>
                {metricLabel(metric, locale)}
              </option>
            ))}
          </select>
          <button className="btn leaderboard-toolbar-btn" onClick={() => setReverseOrder((prev) => !prev)} type="button">
            {reverseOrder ? text.standardOrder : text.reverseOrder}
          </button>
          <button
            className={refreshing ? "btn btn-busy leaderboard-toolbar-btn" : "btn leaderboard-toolbar-btn"}
            disabled={refreshing}
            onClick={() => void loadLeaderboard(true)}
            type="button"
          >
            {refreshing ? text.refreshing : text.refresh}
          </button>
        </div>
      </div>

      <div className="leaderboard-stat-grid reveal-grid mb-4">
        <article className="stat-card w-full">
          <button
            aria-controls="source-filter-panel"
            aria-expanded={sourceFilterPanelOpen}
            className="w-full cursor-pointer text-left"
            onClick={() => setSourceFilterPanelOpen((prev) => !prev)}
            type="button"
          >
            <p className="label mb-2">{text.modelCount}</p>
            <p className="stat-value">
              <AnimatedNumber value={sourceCounts[sourceFilter]} />
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className="mode-chip mode-chip-full">
                {sourceFilterOptions.find((option) => option.value === sourceFilter)?.label || text.filterAll}
              </span>
              <span className="helper-text">{sourceFilterPanelOpen ? text.toggleFilterClose : text.toggleFilterOpen}</span>
            </div>
          </button>
          <div
            className={
              sourceFilterPanelOpen
                ? "mt-3 max-h-32 overflow-hidden border-t border-slate-700/70 pt-3 opacity-100 transition-all duration-300 ease-out translate-y-0"
                : "mt-0 max-h-0 overflow-hidden border-t border-transparent pt-0 opacity-0 transition-all duration-300 ease-out -translate-y-1"
            }
            id="source-filter-panel"
          >
            <div className="flex flex-wrap gap-2">
              {sourceFilterOptions.map((option) => (
                <button
                  className={sourceFilter === option.value ? "filter-chip filter-chip-active" : "filter-chip"}
                  key={option.value}
                  onClick={() => {
                    setSourceFilter(option.value);
                    setExpandedAsrModel("");
                  }}
                  type="button"
                >
                  {option.label} ({option.count})
                </button>
              ))}
            </div>
          </div>
        </article>
        <article className="stat-card">
          <p className="label mb-2">{text.metricCount}</p>
          <p className="stat-value">
            <AnimatedNumber value={payload?.metric_count || 0} />
          </p>
        </article>
      </div>

      <div className="section-card leaderboard-meta-card mb-4 flex flex-wrap items-center justify-between gap-3 p-4 text-xs">
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
        <p className="notice leaderboard-direction-notice mb-4 text-xs">
          {text.direction}: {metricDirectionText(selectedMetric, locale)}
          <span className="mx-2">|</span>
          {text.rowsHint(sortedRows.length)}
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
      ) : sortedRows.length === 0 ? (
        <p className="notice p-4 text-sm text-slate-600">{text.noRowsInFilter}</p>
      ) : (
        <div className="data-table-wrap leaderboard-table-wrap">
          <table className="data-table leaderboard-table min-w-[1320px] bg-transparent">
            <thead>
              <tr>
                <th className="font-semibold">{text.selectedRank}</th>
                <th className="font-semibold">{text.model}</th>
                <th className="font-semibold">{text.sourceType}</th>
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
              {sortedRows.map((row, rowIndex) => {
                const currentRank = selectedRankMap.get(row.model) || 0;
                const isAsrExpanded = expandedAsrModel === row.model;
                return (
                  <Fragment key={row.model}>
                    <tr className={rowIndex % 2 === 0 ? "leaderboard-main-row leaderboard-main-row-even align-top text-sm" : "leaderboard-main-row leaderboard-main-row-odd align-top text-sm"}>
                      <td className="leaderboard-fixed-cell">
                        <span className={rankChipClass(currentRank)}>{currentRank > 0 ? `#${currentRank}` : "-"}</span>
                      </td>
                      <td>
                        <p className="font-headline font-semibold text-slate-100">{row.model}</p>
                      </td>
                      <td className="leaderboard-fixed-cell">
                        {resolveModelSourceType(row.model) === "closed" ? (
                          <span className="mode-chip mode-chip-benchmark">{text.closedSourceLabel}</span>
                        ) : (
                          <span className="mode-chip mode-chip-eval">{text.openSourceLabel}</span>
                        )}
                      </td>
                      {payload.metrics.map((metric) => {
                        const rankMap = rankMapsByMetric.get(metric.key);
                        const rank = rankMap?.get(row.model) || 0;
                        const isAsrMetric = metric.key === "asr";
                        return (
                          <td className={isAsrMetric && isAsrExpanded ? "leaderboard-metric-td leaderboard-metric-td-expanded" : "leaderboard-metric-td"} key={`${row.model}:${metric.key}`}>
                            <div className="leaderboard-metric-cell">
                              <p className="leaderboard-metric-value">{formatMetricValue(row.metrics[metric.key], metric, locale)}</p>
                              <div className="leaderboard-metric-meta">
                                <span className="mode-chip mode-chip-attack">{rank > 0 ? `#${rank}` : "-"}</span>
                                {isAsrMetric ? (
                                  <button
                                    className={isAsrExpanded ? "leaderboard-detail-toggle leaderboard-detail-toggle-active" : "leaderboard-detail-toggle"}
                                    onClick={() => setExpandedAsrModel((prev) => (prev === row.model ? "" : row.model))}
                                    type="button"
                                  >
                                    {isAsrExpanded ? text.hideAsrDetail : text.viewAsrDetail}
                                  </button>
                                ) : null}
                              </div>
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                    {isAsrExpanded ? (
                      <tr className="leaderboard-detail-row align-top text-sm">
                        <td colSpan={3 + payload.metrics.length}>
                          <div className="section-card leaderboard-asr-card p-3">
                            <p className="label mb-2">{text.asrDetailTitle(row.model)}</p>
                            <div className="flex flex-wrap items-center gap-2 text-xs">
                              <span className="mode-chip mode-chip-attack">
                                {text.asrEffective}: {formatPercentValue(row.metrics.asr_effective, locale)}
                              </span>
                              <span className="mode-chip mode-chip-attack">
                                {text.asrStrict}: {formatPercentValue(row.metrics.asr_strict, locale)}
                              </span>
                              <span className="mode-chip mode-chip-attack">
                                {text.asrLegacy}: {formatPercentValue(row.metrics.asr_legacy, locale)}
                              </span>
                            </div>
                          </div>
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
