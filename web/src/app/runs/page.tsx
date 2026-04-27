"use client";

import Link from "next/link";
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
          refreshPausedHidden: "页面隐藏时已暂停自动刷新。",
          refreshHealthy: "自动刷新正常运行。",
          emptyTitle: "还没有任何流水线任务",
          emptyDesc: "可以先创建一个任务，之后这里会自动显示最新状态和阶段进度。",
          createRun: "新建任务",
          openGuide: "查看使用引导",
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
          refreshPausedHidden: "Auto refresh is paused while the page is hidden.",
          refreshHealthy: "Auto refresh is running normally.",
          emptyTitle: "No pipeline runs yet",
          emptyDesc: "Create a run first. This monitor will then keep the latest status and stage progress up to date.",
          createRun: "Create Run",
          openGuide: "Open Guide",
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
  const [manualRefreshing, setManualRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | RunStatus>("all");
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | null>(null);
  const [actionState, setActionState] = useState<{ runId: string; kind: "cancel" | "delete" } | null>(null);
  const [isPageVisible, setIsPageVisible] = useState(true);
  const loadingRef = useRef(false);

  const loadRuns = useCallback(async (mode: "initial" | "manual" | "background" = "initial") => {
    if (loadingRef.current) {
      return;
    }
    loadingRef.current = true;
    if (mode === "manual") {
      setManualRefreshing(true);
    } else if (mode === "initial") {
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
      setManualRefreshing(false);
      loadingRef.current = false;
    }
  }, []);

  useEffect(() => {
    void loadRuns("initial");
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
      void loadRuns("background");
    }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [loadRuns, isPageVisible]);

  useEffect(() => {
    if (isPageVisible) {
      void loadRuns("background");
    }
  }, [isPageVisible, loadRuns]);

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
    return runs
      .filter((run) => {
        if (statusFilter !== "all" && run.status !== statusFilter) {
          return false;
        }
        return true;
      })
      .sort((left, right) => {
        const leftCreatedTime = Date.parse(left.created_at);
        const rightCreatedTime = Date.parse(right.created_at);
        if (Number.isFinite(leftCreatedTime) && Number.isFinite(rightCreatedTime) && leftCreatedTime !== rightCreatedTime) {
          return rightCreatedTime - leftCreatedTime;
        }

        const leftUpdatedTime = Date.parse(left.updated_at);
        const rightUpdatedTime = Date.parse(right.updated_at);
        if (Number.isFinite(leftUpdatedTime) && Number.isFinite(rightUpdatedTime) && leftUpdatedTime !== rightUpdatedTime) {
          return rightUpdatedTime - leftUpdatedTime;
        }

        return right.run_id.localeCompare(left.run_id);
      });
  }, [runs, statusFilter]);

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
        await loadRuns("background");
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
        await loadRuns("background");
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
  const refreshStatusText = !isPageVisible ? text.refreshPausedHidden : text.refreshHealthy;
  const emptyMessage = runs.length
    ? text.noMatch(statusFilterLabel(statusFilter, locale))
    : text.noRuns;

  return (
    <section aria-busy={loading || manualRefreshing} className="panel p-5">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="label">{text.monitor}</p>
          <h2 className="title-gradient font-headline text-2xl font-semibold">{text.title}</h2>
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
      <div className="stat-grid reveal-grid mb-5 md:grid-cols-2 xl:grid-cols-4">
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
      <div className="monitor-toolbar monitor-toolbar-spread mb-4">
        <p className="text-xs text-slate-600">
          {text.lastUpdated}: {lastUpdatedAt ? formatDateTime(lastUpdatedAt, locale) : "-"}
        </p>
        <p className="text-xs text-slate-600">{text.showing(filteredRuns.length, runs.length)}</p>
        <p
          aria-live="polite"
          className={`monitor-status ${isPageVisible ? "monitor-status-quiet" : "monitor-status-warn"}`}
        >
          {refreshStatusText}
        </p>
      </div>
      {error ? (
        <p aria-live="assertive" className="notice notice-error mb-4" role="alert">
          {error}
        </p>
      ) : null}
      {loading ? (
        <p className="text-sm text-slate-600">{text.loading}</p>
      ) : !runs.length ? (
        <div className="empty-state">
          <p className="empty-state-title">{text.emptyTitle}</p>
          <p className="empty-state-copy">{text.emptyDesc}</p>
          <div className="empty-state-actions">
            <Link className="btn btn-primary" href="/runs/new">
              {text.createRun}
            </Link>
            <button className="btn" onClick={() => void loadRuns("manual")} type="button">
              {text.refresh}
            </button>
          </div>
        </div>
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
