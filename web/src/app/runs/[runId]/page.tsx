"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { AnimatedNumber } from "@/components/common/AnimatedNumber";
import { ArtifactTable } from "@/components/runs/ArtifactTable";
import { MetricCards } from "@/components/runs/MetricCards";
import { EvaluationTaskTable } from "@/components/runs/EvaluationTaskTable";
import { RunStatusBadge } from "@/components/runs/RunStatusBadge";
import { StageTimeline } from "@/components/runs/StageTimeline";
import { useI18n } from "@/components/common/LocaleProvider";
import { formatRunMode, formatStageName } from "@/lib/i18n";
import {
  ApiError,
  cancelRun,
  createRun,
  getRun,
  getRunArtifacts,
  getRunLogs,
  getRunMetricTasks,
  getRunMetricsSummary,
  exportRunMetricTaskReport
} from "@/lib/api";
import type {
  Run,
  RunArtifactsResponse,
  RunCreatePayload,
  RunLogsResponse,
  RunMetricTask,
  RunMetricsSummaryResponse
} from "@/lib/types";

type DetailTab = "overview" | "logs" | "artifacts" | "metrics";

function downloadTextFile(filename: string, content: string): void {
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function averageNullable(values: Array<number | null | undefined>): number | null {
  const nums = values.filter((item): item is number => typeof item === "number" && Number.isFinite(item));
  if (!nums.length) {
    return null;
  }
  return nums.reduce((sum, value) => sum + value, 0) / nums.length;
}

function sumNullable(values: Array<number | null | undefined>): number | null {
  const nums = values.filter((item): item is number => typeof item === "number" && Number.isFinite(item));
  if (!nums.length) {
    return null;
  }
  return nums.reduce((sum, value) => sum + value, 0);
}

export default function RunDetailPage() {
  const { locale } = useI18n();
  const text =
    locale === "zh"
      ? {
          loadingRun: "正在加载任务...",
          runNotFound: "未找到任务。",
          runDetail: "任务详情",
          executionTrace: "执行轨迹",
          artifactGraph: "产物图谱",
          monitor: "监控",
          canceling: "取消中...",
          cancel: "取消",
          starting: "启动中...",
          evaluateThisRun: "评估此任务",
          back: "返回",
          autoRefresh: "每 3 秒自动刷新。",
          syncingStatus: "正在同步任务状态...",
          stageSnapshot: "阶段快照",
          totalStages: "总阶段数",
          completed: "已完成",
          failed: "失败",
          config: "配置",
          mode: "模式",
          quickAttackMode: "快速攻击模式",
          enabled: "启用",
          disabled: "禁用",
          targetModel: "目标模型",
          openaiBaseUrl: "OpenAI Base URL",
          quickMethods: "快速方法",
          quickDataset: "快速数据集",
          attackConfig: "攻击配置",
          benchmarkConfig: "基准测试配置",
          evalProfile: "评估配置",
          resultsRoot: "结果根目录",
          resultManifest: "结果清单",
          stages: "阶段",
          stage: "阶段",
          tailLines: "尾部行数",
          refreshing: "刷新中...",
          refresh: "刷新",
          syncingLogs: "正在同步日志...",
          logPath: "日志路径",
          noLogContent: "暂无日志内容。",
          artifacts: "产物",
          metricSummary: "指标汇总",
          metricSummaryHint: "展示聚合指标与任务级细项；若缺少 MDS/Bias/WSL/CM，说明本次评估产物未生成这些维度。",
          metricNeedEvaluate: "该任务未执行评估。点击“评估此任务”生成指标。",
          noMetricSummary: "暂无指标汇总。",
          refreshMetrics: "刷新指标",
          refreshingMetrics: "指标刷新中...",
          tabs: {
            overview: "概览",
            logs: "日志",
            artifacts: "产物",
            metrics: "指标"
          }
        }
      : {
          loadingRun: "Loading run...",
          runNotFound: "Run not found.",
          runDetail: "Run Detail",
          executionTrace: "Execution Trace",
          artifactGraph: "Artifact Graph",
          monitor: "Monitor",
          canceling: "Canceling...",
          cancel: "Cancel",
          starting: "Starting...",
          evaluateThisRun: "Evaluate This Run",
          back: "Back",
          autoRefresh: "Auto refresh every 3s.",
          syncingStatus: "syncing run status...",
          stageSnapshot: "Stage Snapshot",
          totalStages: "Total Stages",
          completed: "Completed",
          failed: "Failed",
          config: "Config",
          mode: "Mode",
          quickAttackMode: "Quick Attack Mode",
          enabled: "enabled",
          disabled: "disabled",
          targetModel: "Target Model",
          openaiBaseUrl: "OpenAI Base URL",
          quickMethods: "Quick Methods",
          quickDataset: "Quick Dataset",
          attackConfig: "Attack Config",
          benchmarkConfig: "Benchmark Config",
          evalProfile: "Eval Profile",
          resultsRoot: "Results Root",
          resultManifest: "Result Manifest",
          stages: "Stages",
          stage: "Stage",
          tailLines: "Tail Lines",
          refreshing: "Refreshing...",
          refresh: "Refresh",
          syncingLogs: "syncing logs...",
          logPath: "Log Path",
          noLogContent: "No log content.",
          artifacts: "Artifacts",
          metricSummary: "Metric Summary",
          metricSummaryHint: "Shows aggregate + task-level metrics. Missing MDS/Bias/WSL/CM usually means this run did not generate those artifacts.",
          metricNeedEvaluate: 'This run did not execute evaluate. Click "Evaluate This Run" to generate metrics.',
          noMetricSummary: "No metric summary generated yet.",
          refreshMetrics: "Refresh Metrics",
          refreshingMetrics: "Refreshing metrics...",
          tabs: {
            overview: "overview",
            logs: "logs",
            artifacts: "artifacts",
            metrics: "metrics"
          }
        };

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
  const [metricTasks, setMetricTasks] = useState<RunMetricTask[]>([]);
  const [metricsLoading, setMetricsLoading] = useState(false);
  const [exportingTaskId, setExportingTaskId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [runRefreshing, setRunRefreshing] = useState(false);
  const [logsRefreshing, setLogsRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [startingEvaluate, setStartingEvaluate] = useState(false);
  const [evaluateProfile, setEvaluateProfile] = useState("full");
  const [isPageVisible, setIsPageVisible] = useState(true);
  const runLoadingRef = useRef(false);
  const logsLoadingRef = useRef(false);

  const isRunning = run?.status === "running" || run?.status === "pending";
  const canEvaluateFromRun =
    !!run && run.status === "succeeded" && run.mode !== "eval_only" && !!run.result_manifest?.trim();

  const loadRun = useCallback(async (background = false) => {
    if (runLoadingRef.current) {
      return;
    }
    runLoadingRef.current = true;
    if (background) {
      setRunRefreshing(true);
    } else {
      setLoading(true);
    }
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
      setRunRefreshing(false);
      runLoadingRef.current = false;
    }
  }, [runId]);

  const loadLogs = useCallback(async (background = false) => {
    if (logsLoadingRef.current) {
      return;
    }
    logsLoadingRef.current = true;
    if (background) {
      setLogsRefreshing(true);
    }
    try {
      const row = await getRunLogs(runId, selectedStage, tailLines);
      setLogs(row);
      setError("");
    } catch (err) {
      const message = err instanceof ApiError ? err.message : String(err);
      setError(message);
    } finally {
      setLogsRefreshing(false);
      logsLoadingRef.current = false;
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
    setMetricsLoading(true);
    try {
      const [summaryRow, tasksRow] = await Promise.all([getRunMetricsSummary(runId), getRunMetricTasks(runId)]);
      setMetrics(summaryRow);
      setMetricTasks(tasksRow.tasks || []);
      setError("");
    } catch (err) {
      const message = err instanceof ApiError ? err.message : String(err);
      setError(message);
    } finally {
      setMetricsLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    void loadRun(false);
  }, [loadRun]);

  useEffect(() => {
    function onVisibilityChange() {
      setIsPageVisible(document.visibilityState === "visible");
    }
    onVisibilityChange();
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => document.removeEventListener("visibilitychange", onVisibilityChange);
  }, []);

  useEffect(() => {
    if (!isPageVisible || !isRunning) {
      return;
    }
    const timer = setInterval(() => {
      void loadRun(true);
    }, 3000);
    return () => clearInterval(timer);
  }, [isPageVisible, isRunning, loadRun]);

  useEffect(() => {
    if (tab !== "logs" || !isPageVisible) {
      return;
    }
    void loadLogs(false);
    const timer = setInterval(() => {
      void loadLogs(true);
    }, 3000);
    return () => clearInterval(timer);
  }, [isPageVisible, tab, loadLogs]);

  useEffect(() => {
    if (tab === "artifacts") {
      void loadArtifacts();
    }
    if (tab === "metrics") {
      void loadMetrics();
    }
  }, [tab, loadArtifacts, loadMetrics]);

  const stageOptions = useMemo(() => run?.stages.map((stage) => stage.stage) || [], [run]);
  const stageStats = useMemo(() => {
    const rows = run?.stages || [];
    const total = rows.length;
    const done = rows.filter((item) => item.status === "succeeded").length;
    const failed = rows.filter((item) => item.status === "failed").length;
    return { total, done, failed };
  }, [run]);

  const derivedMetricSummary = useMemo<Record<string, unknown>>(() => {
    if (!metricTasks.length) {
      return {};
    }

    const scorerSet = new Set<string>();
    metricTasks.forEach((task) => {
      const scorer = (task.scorer || "").trim();
      if (scorer) {
        scorerSet.add(scorer);
      }
    });

    const frrEffectiveValues = metricTasks.map((task) => {
      const frr = task.frr;
      const invalid = task.frr_invalid_rate;
      if (typeof frr !== "number" || !Number.isFinite(frr)) {
        return null;
      }
      if (typeof invalid !== "number" || !Number.isFinite(invalid)) {
        return frr;
      }
      return Math.min(1, Math.max(0, frr + invalid * (1 - frr)));
    });

    const summary: Record<string, unknown> = {
      task_count: metricTasks.length,
      scorer_count: scorerSet.size,
      scorers: Array.from(scorerSet).sort()
    };

    const assignIfPresent = (key: string, value: number | null) => {
      if (value !== null) {
        summary[key] = value;
      }
    };

    assignIfPresent("asr_avg", averageNullable(metricTasks.map((task) => task.asr)));
    assignIfPresent("asr_strict_avg", averageNullable(metricTasks.map((task) => task.asr_strict)));
    assignIfPresent("asr_effective_avg", averageNullable(metricTasks.map((task) => task.asr_effective)));
    assignIfPresent("frr_avg", averageNullable(metricTasks.map((task) => task.frr)));
    assignIfPresent("frr_invalid_rate_avg", averageNullable(metricTasks.map((task) => task.frr_invalid_rate)));
    assignIfPresent("frr_effective_avg", averageNullable(frrEffectiveValues));
    assignIfPresent("total_samples", sumNullable(metricTasks.map((task) => task.total_samples)));
    assignIfPresent("attack_success_samples", sumNullable(metricTasks.map((task) => task.attack_success_samples)));
    assignIfPresent("skipped_samples", sumNullable(metricTasks.map((task) => task.skipped_samples)));

    return summary;
  }, [metricTasks]);

  const mergedMetricSummary = useMemo<Record<string, unknown>>(() => {
    const base: Record<string, unknown> = {
      ...((run?.metric_summary as Record<string, unknown>) || {}),
      ...((metrics?.metric_summary as Record<string, unknown>) || {})
    };
    const merged: Record<string, unknown> = { ...base };
    Object.entries(derivedMetricSummary).forEach(([key, value]) => {
      const current = merged[key];
      if (current === undefined || current === null || current === "") {
        merged[key] = value;
      }
    });
    return merged;
  }, [derivedMetricSummary, metrics?.metric_summary, run?.metric_summary]);
  const frrUnavailable = mergedMetricSummary.frr_denominator_zero === true;

  async function handleCancel() {
    if (!run) {
      return;
    }
    try {
      await cancelRun(run.run_id);
      await loadRun(true);
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

  async function handleExportMetricTask(taskId: string) {
    setExportingTaskId(taskId);
    try {
      const report = await exportRunMetricTaskReport(runId, taskId);
      const filename = report.filename?.trim() || "eval-task-" + runId + "-" + taskId + ".md";
      downloadTextFile(filename, report.content || "");
      setError("");
    } catch (err) {
      const message = err instanceof ApiError ? err.message : String(err);
      setError(message);
    } finally {
      setExportingTaskId(null);
    }
  }

  if (loading) {
    return (
      <section className="panel p-6">
        <p className="text-sm text-slate-600">{text.loadingRun}</p>
      </section>
    );
  }

  if (!run) {
    return (
      <section className="panel p-6">
        <p className="text-sm text-rose-700">{error || text.runNotFound}</p>
      </section>
    );
  }

  return (
    <section aria-busy={loading || runRefreshing || logsRefreshing || metricsLoading} className="space-y-4">
      <div className="panel p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="label mb-1">{text.runDetail}</p>
            <h2 className="title-gradient font-headline text-2xl font-semibold">{run.name}</h2>
            <p className="mono mt-2 text-xs text-slate-600">{run.run_id}</p>
            <div className="hud-strip mt-2">
              <span className="hud-pill">{text.executionTrace}</span>
              <span className="hud-pill">{text.artifactGraph}</span>
              <span className="hud-pill hud-pill-live">
                <span className="refresh-dot" />
                {text.monitor}
              </span>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <RunStatusBadge status={run.status} />
            {isRunning ? (
              <button className={runRefreshing ? "btn btn-busy" : "btn"} disabled={runRefreshing} onClick={() => void handleCancel()} type="button">
                {runRefreshing ? text.canceling : text.cancel}
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
                  {startingEvaluate ? text.starting : text.evaluateThisRun}
                </button>
              </>
            ) : null}
            <Link className="btn" href="/runs">
              {text.back}
            </Link>
          </div>
        </div>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs text-slate-600">{text.autoRefresh}</p>
          {runRefreshing ? (
            <p className="inline-flex items-center gap-2 text-xs text-emerald-700">
              <span className="refresh-dot" />
              {text.syncingStatus}
            </p>
          ) : null}
        </div>
        {run.error ? (
          <p aria-live="assertive" className="notice notice-error mb-3" role="alert">
            {run.error}
          </p>
        ) : null}
        {error ? (
          <p aria-live="assertive" className="notice notice-error" role="alert">
            {error}
          </p>
        ) : null}
        <div className="flex flex-wrap gap-2">
          {(["overview", "logs", "artifacts", "metrics"] as DetailTab[]).map((item) => (
            <button
              className={tab === item ? "tab-btn tab-btn-active" : "tab-btn"}
              key={item}
              onClick={() => setTab(item)}
              type="button"
            >
              {text.tabs[item]}
            </button>
          ))}
        </div>
      </div>

      {tab === "overview" ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <article className="panel p-4 lg:col-span-3">
            <p className="label mb-2">{text.stageSnapshot}</p>
            <div className="stat-grid reveal-grid">
              <article className="stat-card">
                <p className="label mb-2">{text.totalStages}</p>
                <p className="stat-value">
                  <AnimatedNumber value={stageStats.total} />
                </p>
              </article>
              <article className="stat-card">
                <p className="label mb-2">{text.completed}</p>
                <p className="stat-value">
                  <AnimatedNumber value={stageStats.done} />
                </p>
              </article>
              <article className="stat-card">
                <p className="label mb-2">{text.failed}</p>
                <p className="stat-value">
                  <AnimatedNumber value={stageStats.failed} />
                </p>
              </article>
            </div>
          </article>
          <article className="panel p-4 lg:col-span-1">
            <p className="label mb-2">{text.config}</p>
            <dl className="space-y-2 text-sm">
              <div>
                <dt className="label">{text.mode}</dt>
                <dd>{formatRunMode(run.mode, locale)}</dd>
              </div>
              <div>
                <dt className="label">{text.quickAttackMode}</dt>
                <dd>{run.quick_attack_enabled ? text.enabled : text.disabled}</dd>
              </div>
              <div>
                <dt className="label">{text.targetModel}</dt>
                <dd>{run.quick_target_model_name || "-"}</dd>
              </div>
              <div>
                <dt className="label">{text.openaiBaseUrl}</dt>
                <dd className="mono text-xs">{run.quick_openai_base_url || "-"}</dd>
              </div>
              <div>
                <dt className="label">{text.quickMethods}</dt>
                <dd className="mono text-xs">{run.quick_attack_methods?.join(", ") || "-"}</dd>
              </div>
              <div>
                <dt className="label">{text.quickDataset}</dt>
                <dd className="mono text-xs">{run.quick_dataset_key || "-"}</dd>
              </div>
              <div>
                <dt className="label">{text.attackConfig}</dt>
                <dd className="mono text-xs">{run.attack_config_dir || "-"}</dd>
              </div>
              <div>
                <dt className="label">{text.benchmarkConfig}</dt>
                <dd className="mono text-xs">{run.benchmark_config_path || "-"}</dd>
              </div>
              <div>
                <dt className="label">{text.evalProfile}</dt>
                <dd>{run.eval_profile || "-"}</dd>
              </div>
              <div>
                <dt className="label">{text.resultsRoot}</dt>
                <dd className="mono text-xs">{run.results_root}</dd>
              </div>
              <div>
                <dt className="label">{text.resultManifest}</dt>
                <dd className="mono text-xs">{run.result_manifest || "-"}</dd>
              </div>
            </dl>
          </article>
          <article className="panel p-4 lg:col-span-2">
            <p className="label mb-3">{text.stages}</p>
            <StageTimeline stages={run.stages} />
          </article>
        </div>
      ) : null}

      {tab === "logs" ? (
        <article className="panel p-4">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <label className="label" htmlFor="stageSelector">
              {text.stage}
            </label>
            <select
              className="select w-[180px]"
              id="stageSelector"
              onChange={(event) => setSelectedStage(event.target.value)}
              value={selectedStage}
            >
              {stageOptions.map((stageName) => (
                <option key={stageName} value={stageName}>
                  {formatStageName(stageName, locale)}
                </option>
              ))}
            </select>
            <label className="label" htmlFor="tailLines">
              {text.tailLines}
            </label>
            <select
              className="select w-[140px]"
              id="tailLines"
              onChange={(event) => setTailLines(Number(event.target.value))}
              value={tailLines}
            >
              <option value={200}>200</option>
              <option value={400}>400</option>
              <option value={500}>500</option>
              <option value={1000}>1000</option>
            </select>
            <button className={logsRefreshing ? "btn btn-busy" : "btn"} disabled={logsRefreshing} onClick={() => void loadLogs(true)} type="button">
              {logsRefreshing ? text.refreshing : text.refresh}
            </button>
            {logsRefreshing ? (
              <p aria-live="polite" className="inline-flex items-center gap-2 text-xs text-emerald-700">
                <span className="refresh-dot" />
                {text.syncingLogs}
              </p>
            ) : null}
          </div>
          <p className="label mb-2">{text.logPath}</p>
          <p className="mono mb-3 text-xs text-slate-700">{logs?.log_path || "-"}</p>
          <pre className="log-console mono text-xs leading-5">
            {logs?.content || text.noLogContent}
          </pre>
        </article>
      ) : null}

      {tab === "artifacts" ? (
        <article className="panel p-4">
          <p className="label mb-3">{text.artifacts}</p>
          <ArtifactTable artifacts={artifacts?.artifacts || []} />
        </article>
      ) : null}

      {tab === "metrics" ? (
        <article className="panel p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <p className="label">{text.metricSummary}</p>
            <button
              className={metricsLoading ? "btn btn-busy" : "btn"}
              disabled={metricsLoading}
              onClick={() => void loadMetrics()}
              type="button"
            >
              {metricsLoading ? text.refreshingMetrics : text.refreshMetrics}
            </button>
          </div>
          <p className="mb-3 text-xs text-slate-600">{text.metricSummaryHint}</p>
          <MetricCards
            emptyMessage={run.mode === "attack_only" ? text.metricNeedEvaluate : text.noMetricSummary}
            summary={mergedMetricSummary}
          />
          <EvaluationTaskTable
            exportingTaskId={exportingTaskId}
            frrUnavailable={frrUnavailable}
            loading={metricsLoading}
            onExport={(taskId) => void handleExportMetricTask(taskId)}
            tasks={metricTasks}
          />
        </article>
      ) : null}
    </section>
  );
}
