"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArtifactTable } from "@/components/runs/ArtifactTable";
import { MetricCards } from "@/components/runs/MetricCards";
import { RunStatusBadge } from "@/components/runs/RunStatusBadge";
import { StageTimeline } from "@/components/runs/StageTimeline";
import {
  ApiError,
  cancelRun,
  createRun,
  getRun,
  getRunArtifacts,
  getRunLogs,
  getRunMetricsSummary
} from "@/lib/api";
import type { Run, RunArtifactsResponse, RunCreatePayload, RunLogsResponse, RunMetricsSummaryResponse } from "@/lib/types";

type DetailTab = "overview" | "logs" | "artifacts" | "metrics";

export default function RunDetailPage() {
  const params = useParams<{ runId: string }>();
  const router = useRouter();
  const runId = params.runId;

  const [run, setRun] = useState<Run | null>(null);
  const [tab, setTab] = useState<DetailTab>("overview");
  const [tailLines, setTailLines] = useState(400);
  const [selectedStage, setSelectedStage] = useState("attack");
  const [logs, setLogs] = useState<RunLogsResponse | null>(null);
  const [artifacts, setArtifacts] = useState<RunArtifactsResponse | null>(null);
  const [metrics, setMetrics] = useState<RunMetricsSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [startingEvaluate, setStartingEvaluate] = useState(false);
  const [evaluateProfile, setEvaluateProfile] = useState("full");

  const isRunning = run?.status === "running" || run?.status === "pending";
  const canEvaluateFromRun =
    !!run && run.status === "succeeded" && run.mode !== "eval_only" && !!run.result_manifest?.trim();

  const loadRun = useCallback(async () => {
    try {
      const row = await getRun(runId);
      setRun(row);
      setSelectedStage((prev) => {
        if (row.stages.some((stage) => stage.stage === prev)) {
          return prev;
        }
        return row.stages[0]?.stage || "attack";
      });
      setError("");
    } catch (err) {
      const message = err instanceof ApiError ? err.message : String(err);
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [runId]);

  const loadLogs = useCallback(async () => {
    try {
      const row = await getRunLogs(runId, selectedStage, tailLines);
      setLogs(row);
      setError("");
    } catch (err) {
      const message = err instanceof ApiError ? err.message : String(err);
      setError(message);
    }
  }, [runId, selectedStage, tailLines]);

  const loadArtifacts = useCallback(async () => {
    try {
      const row = await getRunArtifacts(runId);
      setArtifacts(row);
      setError("");
    } catch (err) {
      const message = err instanceof ApiError ? err.message : String(err);
      setError(message);
    }
  }, [runId]);

  const loadMetrics = useCallback(async () => {
    try {
      const row = await getRunMetricsSummary(runId);
      setMetrics(row);
      setError("");
    } catch (err) {
      const message = err instanceof ApiError ? err.message : String(err);
      setError(message);
    }
  }, [runId]);

  useEffect(() => {
    void loadRun();
    const timer = setInterval(() => {
      void loadRun();
    }, 3000);
    return () => clearInterval(timer);
  }, [loadRun]);

  useEffect(() => {
    if (tab !== "logs") {
      return;
    }
    void loadLogs();
    const timer = setInterval(() => {
      void loadLogs();
    }, 3000);
    return () => clearInterval(timer);
  }, [tab, loadLogs]);

  useEffect(() => {
    if (tab === "artifacts") {
      void loadArtifacts();
    }
    if (tab === "metrics") {
      void loadMetrics();
    }
  }, [tab, loadArtifacts, loadMetrics]);

  const stageOptions = useMemo(() => run?.stages.map((stage) => stage.stage) || [], [run]);

  async function handleCancel() {
    if (!run) {
      return;
    }
    try {
      await cancelRun(run.run_id);
      await loadRun();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : String(err);
      setError(message);
    }
  }

  async function handleEvaluateFromRun() {
    if (!run || !run.result_manifest.trim()) {
      return;
    }
    const payload: RunCreatePayload = {
      name: `${run.name}-eval-${evaluateProfile}`,
      mode: "eval_only",
      attack_config_dir: "__AUTO__",
      benchmark_config_path: "",
      eval_profile: evaluateProfile,
      results_root: run.results_root || "data/attack_results",
      result_manifest: run.result_manifest,
      quick_attack_enabled: false,
      quick_target_model_name: "gpt-4o-mini",
      quick_openai_base_url: "",
      quick_openai_api_key: "",
      quick_attack_methods: [],
      quick_dataset_key: "teleai_samples_500_500"
    };

    setStartingEvaluate(true);
    try {
      const created = await createRun(payload);
      router.push(`/runs/${created.run_id}`);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : String(err);
      setError(message);
    } finally {
      setStartingEvaluate(false);
    }
  }

  if (loading) {
    return (
      <section className="panel p-6">
        <p className="text-sm text-slate-600">Loading run...</p>
      </section>
    );
  }

  if (!run) {
    return (
      <section className="panel p-6">
        <p className="text-sm text-rose-700">{error || "Run not found."}</p>
      </section>
    );
  }

  return (
    <section className="space-y-4">
      <div className="panel p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="label mb-1">Run Detail</p>
            <h2 className="title-gradient font-headline text-2xl font-semibold">{run.name}</h2>
            <p className="mono mt-2 text-xs text-slate-600">{run.run_id}</p>
          </div>
          <div className="flex items-center gap-2">
            <RunStatusBadge status={run.status} />
            {isRunning ? (
              <button className="btn" onClick={() => void handleCancel()} type="button">
                Cancel
              </button>
            ) : null}
            {canEvaluateFromRun ? (
              <>
                <select
                  className="select w-[120px]"
                  onChange={(event) => setEvaluateProfile(event.target.value)}
                  value={evaluateProfile}
                >
                  <option value="full">full</option>
                  <option value="smoke">smoke</option>
                </select>
                <button className="btn" disabled={startingEvaluate} onClick={() => void handleEvaluateFromRun()} type="button">
                  {startingEvaluate ? "Starting..." : "Evaluate This Run"}
                </button>
              </>
            ) : null}
            <Link className="btn" href="/runs">
              Back
            </Link>
          </div>
        </div>
        {run.error ? <p className="mb-3 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{run.error}</p> : null}
        {error ? <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p> : null}
        <div className="flex flex-wrap gap-2">
          {(["overview", "logs", "artifacts", "metrics"] as DetailTab[]).map((item) => (
            <button
              className={tab === item ? "tab-btn tab-btn-active" : "tab-btn"}
              key={item}
              onClick={() => setTab(item)}
              type="button"
            >
              {item}
            </button>
          ))}
        </div>
      </div>

      {tab === "overview" ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <article className="panel p-4 lg:col-span-1">
            <p className="label mb-2">Config</p>
            <dl className="space-y-2 text-sm">
              <div>
                <dt className="label">Mode</dt>
                <dd>{run.mode}</dd>
              </div>
              <div>
                <dt className="label">Quick Attack Mode</dt>
                <dd>{run.quick_attack_enabled ? "enabled" : "disabled"}</dd>
              </div>
              <div>
                <dt className="label">Target Model</dt>
                <dd>{run.quick_target_model_name || "-"}</dd>
              </div>
              <div>
                <dt className="label">OpenAI Base URL</dt>
                <dd className="mono text-xs">{run.quick_openai_base_url || "-"}</dd>
              </div>
              <div>
                <dt className="label">Quick Methods</dt>
                <dd className="mono text-xs">{run.quick_attack_methods?.join(", ") || "-"}</dd>
              </div>
              <div>
                <dt className="label">Quick Dataset</dt>
                <dd className="mono text-xs">{run.quick_dataset_key || "-"}</dd>
              </div>
              <div>
                <dt className="label">Attack Config</dt>
                <dd className="mono text-xs">{run.attack_config_dir || "-"}</dd>
              </div>
              <div>
                <dt className="label">Benchmark Config</dt>
                <dd className="mono text-xs">{run.benchmark_config_path || "-"}</dd>
              </div>
              <div>
                <dt className="label">Eval Profile</dt>
                <dd>{run.eval_profile || "-"}</dd>
              </div>
              <div>
                <dt className="label">Results Root</dt>
                <dd className="mono text-xs">{run.results_root}</dd>
              </div>
              <div>
                <dt className="label">Result Manifest</dt>
                <dd className="mono text-xs">{run.result_manifest || "-"}</dd>
              </div>
            </dl>
          </article>
          <article className="panel p-4 lg:col-span-2">
            <p className="label mb-3">Stages</p>
            <StageTimeline stages={run.stages} />
          </article>
        </div>
      ) : null}

      {tab === "logs" ? (
        <article className="panel p-4">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <label className="label" htmlFor="stageSelector">
              Stage
            </label>
            <select
              className="select w-[180px]"
              id="stageSelector"
              onChange={(event) => setSelectedStage(event.target.value)}
              value={selectedStage}
            >
              {stageOptions.map((stageName) => (
                <option key={stageName} value={stageName}>
                  {stageName}
                </option>
              ))}
            </select>
            <label className="label" htmlFor="tailLines">
              Tail Lines
            </label>
            <select
              className="select w-[140px]"
              id="tailLines"
              onChange={(event) => setTailLines(Number(event.target.value))}
              value={tailLines}
            >
              <option value={200}>200</option>
              <option value={500}>500</option>
              <option value={1000}>1000</option>
            </select>
            <button className="btn" onClick={() => void loadLogs()} type="button">
              Refresh
            </button>
          </div>
          <p className="label mb-2">Log Path</p>
          <p className="mono mb-3 text-xs text-slate-700">{logs?.log_path || "-"}</p>
          <pre className="log-console mono text-xs leading-5">
            {logs?.content || "No log content."}
          </pre>
        </article>
      ) : null}

      {tab === "artifacts" ? (
        <article className="panel p-4">
          <p className="label mb-3">Artifacts</p>
          <ArtifactTable artifacts={artifacts?.artifacts || []} />
        </article>
      ) : null}

      {tab === "metrics" ? (
        <article className="panel p-4">
          <p className="label mb-3">Metric Summary</p>
          <MetricCards
            emptyMessage={
              run.mode === "attack_only"
                ? 'This run did not execute evaluate. Click "Evaluate This Run" to generate metrics.'
                : "No metric summary generated yet."
            }
            summary={metrics?.metric_summary || run.metric_summary || {}}
          />
        </article>
      ) : null}
    </section>
  );
}
