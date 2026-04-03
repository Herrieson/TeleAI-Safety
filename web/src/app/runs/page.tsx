"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, cancelRun, deleteRun, getRuns } from "@/lib/api";
import { AnimatedNumber } from "@/components/common/AnimatedNumber";
import { RunTable } from "@/components/runs/RunTable";
import { useI18n } from "@/components/common/LocaleProvider";
import { formatDateTime, formatRunStatus } from "@/lib/i18n";
import type { Run, RunStatus } from "@/lib/types";

const POLL_INTERVAL_MS = 5000;

function statusFilterLabel(status: "all" | RunStatus, locale: "zh" | "en") {
  if (status === "all") {
    return locale === "zh" ? "全部" : "All";
  }
  return formatRunStatus(status, locale);
}

export default function RunsPage() {
  const { locale } = useI18n();
  const text =
    locale === "zh"
      ? {
          monitor: "运行监控",
          title: "流水线任务",
          autoRefresh: (seconds: number) => `每 ${seconds} 秒自动刷新，可使用状态筛选快速过滤。`,
          opsDashboard: "运维面板",
          pipelineTelemetry: "流水线遥测",
          liveView: "实时视图",
          status: "状态",
          keyword: "关键词",
          keywordPlaceholder: "按任务名或 run id 搜索",
          clearSearch: "清空",
          refreshing: "刷新中...",
          refresh: "刷新",
          totalRuns: "总任务数",
          active: "进行中",
          failed: "失败",
          successRate: "成功率",
          lastUpdated: "最近更新",
          syncing: "同步中...",
          loading: "正在加载任务...",
          showing: (visible: number, total: number) => `显示 ${visible} / ${total} 条任务`,
          noMatch: (label: string) => `没有匹配“${label}”筛选条件的任务。`,
          noMatchKeyword: (keyword: string) => `没有匹配关键词“${keyword}”的任务。`,
          noMatchCombined: (label: string, keyword: string) => `没有匹配“${label}”且包含“${keyword}”的任务。`,
          noRuns: "暂无任务。",
          deleteConfirm: (runId: string) => `确认删除任务 ${runId} 以及后端产物吗？`
        }
      : {
          monitor: "Run Monitor",
          title: "Pipeline Runs",
          autoRefresh: (seconds: number) => `Auto refresh every ${seconds}s. Use status chips for quick filtering.`,
          opsDashboard: "Ops Dashboard",
          pipelineTelemetry: "Pipeline Telemetry",
          liveView: "Live View",
          status: "Status",
          keyword: "Keyword",
          keywordPlaceholder: "Search by run name or run id",
          clearSearch: "Clear",
          refreshing: "Refreshing...",
          refresh: "Refresh",
          totalRuns: "Total Runs",
          active: "Active",
          failed: "Failed",
          successRate: "Success Rate",
          lastUpdated: "Last updated",
          syncing: "syncing...",
          loading: "Loading runs...",
          showing: (visible: number, total: number) => `Showing ${visible} / ${total} runs`,
          noMatch: (label: string) => `No runs matched filter "${label}".`,
          noMatchKeyword: (keyword: string) => `No runs matched keyword "${keyword}".`,
          noMatchCombined: (label: string, keyword: string) => `No runs matched filter "${label}" with keyword "${keyword}".`,
          noRuns: "No runs yet.",
          deleteConfirm: (runId: string) => `Delete run ${runId} and its backend artifacts?`
        };

  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | RunStatus>("all");
  const [keyword, setKeyword] = useState("");
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | null>(null);
  const [actionState, setActionState] = useState<{ runId: string; kind: "cancel" | "delete" } | null>(null);
  const [isPageVisible, setIsPageVisible] = useState(true);
  const loadingRef = useRef(false);

  const loadRuns = useCallback(async (background = false) => {
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
      const data = await getRuns();
      setRuns(data);
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
    void loadRuns(false);
  }, [loadRuns]);

  useEffect(() => {
    function onVisibilityChange() {
      setIsPageVisible(document.visibilityState === "visible");
    }
    onVisibilityChange();
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => document.removeEventListener("visibilitychange", onVisibilityChange);
  }, []);

  useEffect(() => {
    if (!isPageVisible) {
      return;
    }
    const timer = setInterval(() => {
      void loadRuns(true);
    }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [loadRuns, isPageVisible]);

  const statusCounts = useMemo<Record<"all" | RunStatus, number>>(() => {
    const counts: Record<"all" | RunStatus, number> = {
      all: runs.length,
      pending: 0,
      running: 0,
      succeeded: 0,
      failed: 0,
      canceled: 0
    };
    runs.forEach((run) => {
      counts[run.status] += 1;
    });
    return counts;
  }, [runs]);

  const filteredRuns = useMemo(() => {
    const query = keyword.trim().toLowerCase();
    return runs
      .filter((run) => {
        if (statusFilter !== "all" && run.status !== statusFilter) {
          return false;
        }
        if (!query) {
          return true;
        }
        return run.name.toLowerCase().includes(query) || run.run_id.toLowerCase().includes(query);
      })
      .sort((left, right) => {
        const leftTime = Date.parse(left.updated_at);
        const rightTime = Date.parse(right.updated_at);
        if (!Number.isFinite(leftTime) || !Number.isFinite(rightTime)) {
          return right.updated_at.localeCompare(left.updated_at);
        }
        return rightTime - leftTime;
      });
  }, [keyword, runs, statusFilter]);

  const runStats = useMemo(() => {
    const total = runs.length;
    const active = runs.filter((run) => run.status === "running" || run.status === "pending").length;
    const succeeded = runs.filter((run) => run.status === "succeeded").length;
    const failures = runs.filter((run) => run.status === "failed").length;
    const successRate = total ? (succeeded / total) * 100 : 0;
    return { total, active, failures, successRate };
  }, [runs]);

  const handleCancel = useCallback(
    async (runId: string) => {
      setActionState({ runId, kind: "cancel" });
      try {
        await cancelRun(runId);
        await loadRuns(true);
      } catch (err) {
        const message = err instanceof ApiError ? err.message : String(err);
        setError(message);
      } finally {
        setActionState(null);
      }
    },
    [loadRuns]
  );

  const handleDelete = useCallback(
    async (runId: string) => {
      if (!window.confirm(text.deleteConfirm(runId))) {
        return;
      }
      setActionState({ runId, kind: "delete" });
      try {
        await deleteRun(runId);
        await loadRuns(true);
      } catch (err) {
        const message = err instanceof ApiError ? err.message : String(err);
        setError(message);
      } finally {
        setActionState(null);
      }
    },
    [loadRuns, text]
  );

  const filterValues: Array<"all" | RunStatus> = ["all", "pending", "running", "succeeded", "failed", "canceled"];
  const trimmedKeyword = keyword.trim();
  const emptyMessage = runs.length
    ? trimmedKeyword && statusFilter !== "all"
      ? text.noMatchCombined(statusFilterLabel(statusFilter, locale), trimmedKeyword)
      : trimmedKeyword
        ? text.noMatchKeyword(trimmedKeyword)
        : text.noMatch(statusFilterLabel(statusFilter, locale))
    : text.noRuns;

  return (
    <section aria-busy={loading || refreshing} className="panel p-5">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="label">{text.monitor}</p>
          <h2 className="title-gradient font-headline text-2xl font-semibold">{text.title}</h2>
          <p className="mt-1 text-sm text-slate-600">{text.autoRefresh(Math.floor(POLL_INTERVAL_MS / 1000))}</p>
          <div className="hud-strip mt-2">
            <span className="hud-pill">{text.opsDashboard}</span>
            <span className="hud-pill">{text.pipelineTelemetry}</span>
            <span className="hud-pill hud-pill-live">
              <span className="refresh-dot" />
              {text.liveView}
            </span>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="label" htmlFor="statusFilter">
            {text.status}
          </label>
          <select
            className="select w-full min-w-[150px] sm:w-[170px]"
            id="statusFilter"
            onChange={(event) => setStatusFilter(event.target.value as "all" | RunStatus)}
            value={statusFilter}
          >
            {filterValues.map((value) => (
              <option key={value} value={value}>
                {statusFilterLabel(value, locale)}
              </option>
            ))}
          </select>
          <label className="label" htmlFor="runKeywordFilter">
            {text.keyword}
          </label>
          <input
            className="input w-full min-w-[220px] sm:w-[260px]"
            id="runKeywordFilter"
            onChange={(event) => setKeyword(event.target.value)}
            placeholder={text.keywordPlaceholder}
            value={keyword}
          />
          {keyword ? (
            <button className="btn" onClick={() => setKeyword("")} type="button">
              {text.clearSearch}
            </button>
          ) : null}
          <button className={refreshing ? "btn btn-busy" : "btn"} disabled={refreshing} onClick={() => void loadRuns(true)} type="button">
            {refreshing ? text.refreshing : text.refresh}
          </button>
        </div>
      </div>
      <div className="mb-4 filter-row">
        {filterValues.map((value) => (
          <button
            className={statusFilter === value ? "filter-chip filter-chip-active" : "filter-chip"}
            key={value}
            onClick={() => setStatusFilter(value)}
            type="button"
          >
            {statusFilterLabel(value, locale)} ({statusCounts[value]})
          </button>
        ))}
      </div>
      <div className="stat-grid reveal-grid mb-5">
        <article className="stat-card">
          <p className="label mb-2">{text.totalRuns}</p>
          <p className="stat-value">
            <AnimatedNumber value={runStats.total} />
          </p>
        </article>
        <article className="stat-card">
          <p className="label mb-2">{text.active}</p>
          <p className="stat-value">
            <AnimatedNumber value={runStats.active} />
          </p>
        </article>
        <article className="stat-card">
          <p className="label mb-2">{text.failed}</p>
          <p className="stat-value">
            <AnimatedNumber value={runStats.failures} />
          </p>
        </article>
        <article className="stat-card">
          <p className="label mb-2">{text.successRate}</p>
          <p className="stat-value">
            <AnimatedNumber decimals={1} suffix="%" value={runStats.successRate} />
          </p>
        </article>
      </div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-slate-600">
          {text.lastUpdated}: {lastUpdatedAt ? formatDateTime(lastUpdatedAt, locale) : "-"}
        </p>
        <p className="text-xs text-slate-600">{text.showing(filteredRuns.length, runs.length)}</p>
        {refreshing ? (
          <p aria-live="polite" className="inline-flex items-center gap-2 text-xs text-emerald-700">
            <span className="refresh-dot" />
            {text.syncing}
          </p>
        ) : null}
      </div>
      {error ? (
        <p aria-live="assertive" className="notice notice-error mb-4" role="alert">
          {error}
        </p>
      ) : null}
      {loading ? (
        <p className="text-sm text-slate-600">{text.loading}</p>
      ) : (
        <RunTable
          actionKind={actionState?.kind || null}
          actionRunId={actionState?.runId}
          emptyMessage={emptyMessage}
          onCancel={handleCancel}
          onDelete={handleDelete}
          runs={filteredRuns}
        />
      )}
    </section>
  );
}
