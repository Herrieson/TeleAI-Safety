"use client";

import type { Dispatch, SetStateAction } from "react";
import { getAttackMethodInfo } from "@/lib/attackMethodInfo";
import { formatRunMode, formatStageName, type Locale } from "@/lib/i18n";
import type { NewRunText } from "@/lib/newRunText";
import type { Run, RunCreatePayload, RunMode } from "@/lib/types";

type AdvancedModeFormProps = {
  locale: Locale;
  text: NewRunText;
  payload: RunCreatePayload;
  setPayload: Dispatch<SetStateAction<RunCreatePayload>>;
  runModeOptions: RunMode[];
  methodOptions: string[];
  selectedCount: number;
  benchmarkWillRun: boolean;
  benchmarkNeedsStandaloneTarget: boolean;
  manifestSourceRuns: Run[];
  manifestSourceRunId: string;
  setManifestSourceRunId: Dispatch<SetStateAction<string>>;
  selectedManifestSourceRun: Run | null;
  stagePreview: string[];
  previewWarnings: string[];
  isAttackMode: boolean;
  isBenchmarkMode: boolean;
  isEvaluateMode: boolean;
  error: string;
  initializing: boolean;
  submitting: boolean;
  onReset: () => void;
  onToggleMethod: (method: string) => void;
};

export function AdvancedModeForm({
  locale,
  text,
  payload,
  setPayload,
  runModeOptions,
  methodOptions,
  selectedCount,
  benchmarkWillRun,
  benchmarkNeedsStandaloneTarget,
  manifestSourceRuns,
  manifestSourceRunId,
  setManifestSourceRunId,
  selectedManifestSourceRun,
  stagePreview,
  previewWarnings,
  isAttackMode,
  isBenchmarkMode,
  isEvaluateMode,
  error,
  initializing,
  submitting,
  onReset,
  onToggleMethod
}: AdvancedModeFormProps) {
  const quickAttackActive = isAttackMode;
  const isFullPipelineMode = payload.mode === "full_pipeline";

  return (
    <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
      <div className="space-y-5 xl:col-span-8 reveal-grid">
        <article className="section-card">
          <p className="label mb-3">{text.basicSetup}</p>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <label>
              <span className="label mb-1 block">{text.runNameOptional}</span>
              <input
                className="input"
                onChange={(event) => setPayload((prev) => ({ ...prev, name: event.target.value }))}
                placeholder="e.g. gpt4o-mini-nightly"
                value={payload.name}
              />
            </label>
            <label data-tour="advanced-run-mode">
              <span className="label mb-1 block">{text.mode}</span>
              <select
                className="select"
                onChange={(event) => {
                  const nextMode = event.target.value as RunMode;
                  setPayload((prev) => ({
                    ...prev,
                    mode: nextMode,
                    quick_attack_enabled: nextMode === "attack_only" || nextMode === "full_pipeline",
                    attack_config_dir: nextMode === "attack_only" || nextMode === "full_pipeline" ? "__AUTO__" : prev.attack_config_dir
                  }));
                  if (nextMode !== "eval_only") {
                    setManifestSourceRunId("");
                  }
                }}
                value={payload.mode}
              >
                {runModeOptions.map((option) => (
                  <option key={option} value={option}>
                    {formatRunMode(option, locale)}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </article>

        {isAttackMode ? (
          <article className="section-card">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <p className="label">{text.attackSettings}</p>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-1 gap-4">
                <label data-tour="advanced-target-model">
                  <span className="label mb-1 block">{text.targetModelName}</span>
                  <input
                    className="input"
                    onChange={(event) =>
                      setPayload((prev) => ({
                        ...prev,
                        quick_target_model_name: event.target.value
                      }))
                    }
                    placeholder="gpt-4o-mini"
                    value={payload.quick_target_model_name}
                  />
                </label>
              </div>

              <details className="tech-subpanel p-3">
                <summary className="cursor-pointer text-sm font-medium text-slate-700">
                  {text.targetApiCreds} {benchmarkWillRun ? text.requiredForBenchmark : text.optional}
                </summary>
                <div className="mt-3 space-y-3">
                  <label>
                    <span className="label mb-1 block">{text.openaiBaseUrl}</span>
                    <input
                      className="input mono"
                      onChange={(event) =>
                        setPayload((prev) => ({
                          ...prev,
                          quick_openai_base_url: event.target.value
                        }))
                      }
                      placeholder="https://api.openai.com/v1"
                      value={payload.quick_openai_base_url}
                    />
                  </label>
                  <label>
                    <span className="label mb-1 block">{text.openaiApiKey}</span>
                    <input
                      className="input mono"
                      onChange={(event) =>
                        setPayload((prev) => ({
                          ...prev,
                          quick_openai_api_key: event.target.value
                        }))
                      }
                      placeholder="sk-..."
                      type="password"
                      value={payload.quick_openai_api_key}
                    />
                  </label>
                </div>
              </details>

              <details className="tech-subpanel p-3" data-tour="advanced-attack-methods" open={selectedCount === 0}>
                <summary className="cursor-pointer text-sm font-medium text-slate-700">
                  {text.attackMethods} ({selectedCount} {text.selected} / {methodOptions.length})
                </summary>
                <div className="mt-3 space-y-3">
                  <div className="flex items-center gap-2">
                    <button
                      className="btn"
                      onClick={() => setPayload((prev) => ({ ...prev, quick_attack_methods: [...methodOptions] }))}
                      type="button"
                    >
                      {text.selectAll}
                    </button>
                    <button className="btn" onClick={() => setPayload((prev) => ({ ...prev, quick_attack_methods: [] }))} type="button">
                      {text.clear}
                    </button>
                  </div>
                  <div className="method-grid">
                    {methodOptions.map((method) => {
                      const selected = payload.quick_attack_methods.includes(method);
                      const methodInfo = getAttackMethodInfo(method);
                      const methodSummary = locale === "zh" ? methodInfo.summary_zh : methodInfo.summary_en;
                      return (
                        <div className="method-chip-wrap" key={method}>
                          <label className={selected ? "method-chip method-chip-active" : "method-chip"}>
                            <input checked={selected} className="sr-only" onChange={() => onToggleMethod(method)} type="checkbox" />
                            <span>{method}</span>
                          </label>
                          <div className="method-tip-card" role="tooltip">
                            <p className="method-tip-title mono">{method}</p>
                            <p className="method-tip-line">
                              <span className="method-tip-label">{text.methodIntro}</span>
                              <span>{methodSummary}</span>
                            </p>
                            <div className="method-tip-links">
                              {methodInfo.paper_url ? (
                                <a href={methodInfo.paper_url} rel="noreferrer noopener" target="_blank">
                                  {text.methodPaper}
                                </a>
                              ) : null}
                              {methodInfo.repo_url ? (
                                <a href={methodInfo.repo_url} rel="noreferrer noopener" target="_blank">
                                  {text.methodRepo}
                                </a>
                              ) : null}
                              {methodInfo.paper_url || methodInfo.repo_url ? null : (
                                <span className="method-tip-empty">{text.methodNoRef}</span>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </details>
            </div>
          </article>
        ) : null}

        {isFullPipelineMode ? (
          <article className="section-card">
            <p className="label mb-3">{text.stages}</p>
            <p className="tech-subpanel p-3 text-sm text-slate-700">{text.pipelineAutoFollowup}</p>
          </article>
        ) : null}

        {isBenchmarkMode && !isFullPipelineMode ? (
          <article className="section-card">
            <p className="label mb-3">{text.benchmarkSettings}</p>
            <p className="tech-subpanel p-3 text-sm text-slate-700">{text.runtimeConfigHint}</p>

            {benchmarkNeedsStandaloneTarget ? (
              <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
                <label>
                  <span className="label mb-1 block">{text.targetModelName}</span>
                  <input
                    className="input"
                    onChange={(event) => setPayload((prev) => ({ ...prev, quick_target_model_name: event.target.value }))}
                    placeholder="gpt-4o-mini"
                    value={payload.quick_target_model_name}
                  />
                </label>
                <label>
                  <span className="label mb-1 block">{text.targetOpenaiBaseUrl}</span>
                  <input
                    className="input mono"
                    onChange={(event) => setPayload((prev) => ({ ...prev, quick_openai_base_url: event.target.value }))}
                    placeholder="https://api.openai.com/v1"
                    value={payload.quick_openai_base_url}
                  />
                </label>
                <label className="md:col-span-2">
                  <span className="label mb-1 block">{text.targetOpenaiApiKey}</span>
                  <input
                    className="input mono"
                    onChange={(event) => setPayload((prev) => ({ ...prev, quick_openai_api_key: event.target.value }))}
                    placeholder="sk-..."
                    type="password"
                    value={payload.quick_openai_api_key}
                  />
                </label>
              </div>
            ) : (
              <p className="tech-subpanel mt-4 p-3 text-sm text-slate-700">{text.benchmarkReuseHint}</p>
            )}
          </article>
        ) : null}

        {isEvaluateMode && !isFullPipelineMode ? (
          <article className="section-card">
            <p className="label mb-3">{text.evaluateSettings}</p>
            <div className="grid grid-cols-1 gap-4">
              <label>
                <span className="label mb-1 block">{text.evalProfile}</span>
                <select
                  className="select"
                  onChange={(event) => setPayload((prev) => ({ ...prev, eval_profile: event.target.value }))}
                  value={payload.eval_profile}
                >
                  <option value="full">full</option>
                  <option value="smoke">smoke</option>
                </select>
              </label>
            </div>

            {payload.mode === "eval_only" ? (
              <div className="mt-4 space-y-4">
                <label>
                  <span className="label mb-1 block">{text.useExistingRunManifest}</span>
                  <select className="select" onChange={(event) => setManifestSourceRunId(event.target.value)} value={manifestSourceRunId}>
                    {manifestSourceRuns.length ? null : <option value="">{text.manualManifestPath}</option>}
                    {manifestSourceRuns.map((item) => (
                      <option key={item.run_id} value={item.run_id}>
                        {item.name} ({item.run_id.slice(0, 8)})
                      </option>
                    ))}
                  </select>
                </label>
                {selectedManifestSourceRun ? (
                  <p className="tech-subpanel p-3 text-sm text-slate-700">
                    {selectedManifestSourceRun.name} ({selectedManifestSourceRun.run_id.slice(0, 8)})
                  </p>
                ) : (
                  <details className="tech-subpanel p-3">
                    <summary className="cursor-pointer text-sm font-medium text-slate-700">{text.manualManifestPath}</summary>
                    <div className="mt-3">
                      <label>
                        <span className="label mb-1 block">{text.resultManifestPath}</span>
                        <input
                          className="input mono"
                          onChange={(event) => setPayload((prev) => ({ ...prev, result_manifest: event.target.value }))}
                          placeholder="data/attack_results/runs/<run_id>/manifests/<name>.txt"
                          value={payload.result_manifest}
                        />
                      </label>
                    </div>
                  </details>
                )}
              </div>
            ) : null}
          </article>
        ) : null}

        {error ? (
          <p aria-live="assertive" className="notice notice-error" role="alert">
            {error}
          </p>
        ) : null}

        <div className="flex flex-wrap items-center gap-2">
          <button
            className={submitting ? "btn btn-primary btn-busy" : "btn btn-primary"}
            data-tour="advanced-submit"
            disabled={submitting || initializing}
            type="submit"
          >
            {submitting ? text.submitting : initializing ? text.preparing : modeSubmitLabel(payload.mode, locale)}
          </button>
          <button className="btn" onClick={onReset} type="button">
            {text.reset}
          </button>
        </div>
      </div>

      <aside className="space-y-4 xl:col-span-4 xl:sticky xl:top-6 xl:self-start reveal-grid">
        <article className="stat-card">
          <p className="label mb-2">{text.runPreview}</p>
          <dl className="space-y-2 text-sm text-slate-700">
            <div>
              <dt className="label">{text.mode}</dt>
              <dd>{formatRunMode(payload.mode, locale)}</dd>
            </div>
            <div>
              <dt className="label">{text.stages}</dt>
              <dd className="mono text-xs">{stagePreview.join(" -> ") || "-"}</dd>
            </div>
            <div>
              <dt className="label">{text.targetModel}</dt>
              <dd>{payload.quick_target_model_name || "-"}</dd>
            </div>
            <div>
              <dt className="label">{text.attackMethodsCount}</dt>
              <dd>{quickAttackActive ? selectedCount : 0}</dd>
            </div>
            <div>
              <dt className="label">{text.benchmarkConfig}</dt>
              <dd className="text-xs">{benchmarkWillRun ? text.runtimeConfigHint : "-"}</dd>
            </div>
          </dl>
        </article>

        <article className="stat-card">
          <p className="label mb-2">{text.checklist}</p>
          {previewWarnings.length ? (
            <div className="notice notice-warn">
              <ul className="space-y-1 text-sm">
                {previewWarnings.map((item) => (
                  <li key={item}>- {item}</li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="notice notice-good text-sm">{text.formLooksGood}</p>
          )}
        </article>
      </aside>
    </div>
  );
}

function modeSubmitLabel(mode: RunMode, locale: Locale): string {
  if (locale === "zh") {
    if (mode === "attack_only") {
      return "启动攻击任务";
    }
    if (mode === "eval_only") {
      return "启动评估任务";
    }
    if (mode === "benchmark_only") {
      return "启动基准测试任务";
    }
    return "启动完整流水线";
  }

  if (mode === "attack_only") {
    return "Start Attack Run";
  }
  if (mode === "eval_only") {
    return "Start Eval Run";
  }
  if (mode === "benchmark_only") {
    return "Start Benchmark Run";
  }
  return "Start Full Pipeline";
}
