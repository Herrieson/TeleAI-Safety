"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, cancelRun, deleteRun, getRuns } from "@/lib/api";
import { AnimatedNumber } from "@/components/common/AnimatedNumber";
import { RunTable } from "@/components/runs/RunTable";
import type { Run, RunStatus } from "@/lib/types";

const POLL_INTERVAL_MS = 5000;

export default function RunsPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | RunStatus>("all");
  const [lastUpdatedAt, setLastUpdatedAt] = useState("");
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
      setLastUpdatedAt(new Date().toLocaleString());
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

  const filteredRuns = useMemo(() => {
    if (statusFilter === "all") {
      return runs;
    }
    return runs.filter((run) => run.status === statusFilter);
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
      if (!window.confirm(`Delete run ${runId} and its backend artifacts?`)) {
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
    [loadRuns]
  );

  const filterOptions: Array<{ label: string; value: "all" | RunStatus }> = [
    { label: "all", value: "all" },
    { label: "pending", value: "pending" },
    { label: "running", value: "running" },
    { label: "succeeded", value: "succeeded" },
    { label: "failed", value: "failed" },
    { label: "canceled", value: "canceled" }
  ];

  return (
    <section aria-busy={loading || refreshing} className="panel p-5">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="label">Run Monitor</p>
          <h2 className="title-gradient font-headline text-2xl font-semibold">Pipeline Runs</h2>
          <p className="mt-1 text-sm text-slate-600">
            Auto refresh every {Math.floor(POLL_INTERVAL_MS / 1000)}s. Use status chips for quick filtering.
          </p>
          <div className="hud-strip mt-2">
            <span className="hud-pill">Ops Dashboard</span>
            <span className="hud-pill">Pipeline Telemetry</span>
            <span className="hud-pill hud-pill-live">
              <span className="refresh-dot" />
              Live View
            </span>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="label" htmlFor="statusFilter">
            Status
          </label>
          <select
            className="select w-full min-w-[150px] sm:w-[170px]"
            id="statusFilter"
            onChange={(event) => setStatusFilter(event.target.value as "all" | RunStatus)}
            value={statusFilter}
          >
            <option value="all">All</option>
            <option value="pending">Pending</option>
            <option value="running">Running</option>
            <option value="succeeded">Succeeded</option>
            <option value="failed">Failed</option>
            <option value="canceled">Canceled</option>
          </select>
          <button className={refreshing ? "btn btn-busy" : "btn"} disabled={refreshing} onClick={() => void loadRuns(true)} type="button">
            {refreshing ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </div>
      <div className="mb-4 filter-row">
        {filterOptions.map((option) => (
          <button
            className={statusFilter === option.value ? "filter-chip filter-chip-active" : "filter-chip"}
            key={option.value}
            onClick={() => setStatusFilter(option.value)}
            type="button"
          >
            {option.label}
          </button>
        ))}
      </div>
      <div className="stat-grid reveal-grid mb-5">
        <article className="stat-card">
          <p className="label mb-2">Total Runs</p>
          <p className="stat-value">
            <AnimatedNumber value={runStats.total} />
          </p>
        </article>
        <article className="stat-card">
          <p className="label mb-2">Active</p>
          <p className="stat-value">
            <AnimatedNumber value={runStats.active} />
          </p>
        </article>
        <article className="stat-card">
          <p className="label mb-2">Failed</p>
          <p className="stat-value">
            <AnimatedNumber value={runStats.failures} />
          </p>
        </article>
        <article className="stat-card">
          <p className="label mb-2">Success Rate</p>
          <p className="stat-value">
            <AnimatedNumber decimals={1} suffix="%" value={runStats.successRate} />
          </p>
        </article>
      </div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-slate-600">Last updated: {lastUpdatedAt || "-"}</p>
        {refreshing ? (
          <p aria-live="polite" className="inline-flex items-center gap-2 text-xs text-emerald-700">
            <span className="refresh-dot" />
            syncing...
          </p>
        ) : null}
      </div>
      {error ? (
        <p aria-live="assertive" className="notice notice-error mb-4" role="alert">
          {error}
        </p>
      ) : null}
      {loading ? (
        <p className="text-sm text-slate-600">Loading runs...</p>
      ) : (
        <RunTable
          actionKind={actionState?.kind || null}
          actionRunId={actionState?.runId}
          emptyMessage={runs.length ? `No runs matched filter "${statusFilter}".` : "No runs yet."}
          onCancel={handleCancel}
          onDelete={handleDelete}
          runs={filteredRuns}
        />
      )}
    </section>
  );
}
