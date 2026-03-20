"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, cancelRun, deleteRun, getRuns } from "@/lib/api";
import { RunTable } from "@/components/runs/RunTable";
import type { Run, RunStatus } from "@/lib/types";

const POLL_INTERVAL_MS = 5000;

export default function RunsPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | RunStatus>("all");

  const loadRuns = useCallback(async () => {
    try {
      const data = await getRuns();
      setRuns(data);
      setError("");
    } catch (err) {
      const message = err instanceof ApiError ? err.message : String(err);
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadRuns();
    const timer = setInterval(() => {
      void loadRuns();
    }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [loadRuns]);

  const filteredRuns = useMemo(() => {
    if (statusFilter === "all") {
      return runs;
    }
    return runs.filter((run) => run.status === statusFilter);
  }, [runs, statusFilter]);

  const runStats = useMemo(() => {
    const total = runs.length;
    const active = runs.filter((run) => run.status === "running" || run.status === "pending").length;
    const failures = runs.filter((run) => run.status === "failed").length;
    return { total, active, failures };
  }, [runs]);

  const handleCancel = useCallback(
    async (runId: string) => {
      try {
        await cancelRun(runId);
        await loadRuns();
      } catch (err) {
        const message = err instanceof ApiError ? err.message : String(err);
        setError(message);
      }
    },
    [loadRuns]
  );

  const handleDelete = useCallback(
    async (runId: string) => {
      if (!window.confirm(`Delete run ${runId} and its backend artifacts?`)) {
        return;
      }
      try {
        await deleteRun(runId);
        await loadRuns();
      } catch (err) {
        const message = err instanceof ApiError ? err.message : String(err);
        setError(message);
      }
    },
    [loadRuns]
  );

  return (
    <section className="panel p-5">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="label">Run Monitor</p>
          <h2 className="title-gradient font-headline text-2xl font-semibold">Pipeline Runs</h2>
        </div>
        <div className="flex items-center gap-2">
          <label className="label" htmlFor="statusFilter">
            Status
          </label>
          <select
            className="select w-[170px]"
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
          <button className="btn" onClick={() => void loadRuns()} type="button">
            Refresh
          </button>
        </div>
      </div>
      <div className="stat-grid mb-5">
        <article className="stat-card">
          <p className="label mb-2">Total Runs</p>
          <p className="stat-value">{runStats.total}</p>
        </article>
        <article className="stat-card">
          <p className="label mb-2">Active</p>
          <p className="stat-value">{runStats.active}</p>
        </article>
        <article className="stat-card">
          <p className="label mb-2">Failed</p>
          <p className="stat-value">{runStats.failures}</p>
        </article>
      </div>
      {error ? <p className="mb-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p> : null}
      {loading ? (
        <p className="text-sm text-slate-600">Loading runs...</p>
      ) : (
        <RunTable onCancel={handleCancel} onDelete={handleDelete} runs={filteredRuns} />
      )}
    </section>
  );
}
