"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ApiError,
  getAttackConfigOptions,
  getBenchmarkConfigOptions,
  createRun,
  getQuickAttackDatasets,
  getQuickAttackMethods,
  getRuns
} from "@/lib/api";
import type { QuickAttackDataset, Run, RunCreatePayload, RunMode } from "@/lib/types";

const fallbackMethodOptions = [
  "artprompt",
  "cipher",
  "deep_inception",
  "dra",
  "jailbroken",
  "morpheus_gapfill",
  "pair",
  "rene"
];

const defaultPayload: RunCreatePayload = {
  name: "",
  mode: "attack_only",
  attack_config_dir: "__AUTO__",
  benchmark_config_path: "",
  eval_profile: "full",
  results_root: "data/attack_results",
  result_manifest: "",
  quick_attack_enabled: true,
  quick_target_model_name: "gpt-4o-mini",
  quick_openai_base_url: "",
  quick_openai_api_key: "",
  quick_attack_methods: ["pair", "cipher", "rene"],
  quick_dataset_key: "teleai_samples_500_500"
};

const runModeOptions: { value: RunMode; label: string }[] = [
  { value: "attack_only", label: "Attack Only" },
  { value: "eval_only", label: "Eval Only" },
  { value: "full_pipeline", label: "Full Pipeline" },
  { value: "benchmark_only", label: "Benchmark Only" }
];

function modeSubmitLabel(mode: RunMode): string {
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

export default function NewRunPage() {
  const router = useRouter();
  const [payload, setPayload] = useState<RunCreatePayload>(defaultPayload);
  const [submitting, setSubmitting] = useState(false);
  const [initializing, setInitializing] = useState(true);
  const [error, setError] = useState("");
  const [methodOptions, setMethodOptions] = useState<string[]>(fallbackMethodOptions);
  const [datasetOptions, setDatasetOptions] = useState<QuickAttackDataset[]>([
    {
      key: "teleai_samples_500_500",
      name: "TeleAI Samples 500/500",
      path: "data/txt/teleai_samples_500_500.jsonl",
      description: "Default text benchmark set with balanced risky and safe samples.",
      exists: true
    }
  ]);
  const [manifestSourceRuns, setManifestSourceRuns] = useState<Run[]>([]);
  const [manifestSourceRunId, setManifestSourceRunId] = useState("");
  const [attackConfigPathOptions, setAttackConfigPathOptions] = useState<string[]>([
    "configs/gpt-5.4",
    "configs/gpt-5",
    "configs/gpt-4o"
  ]);
  const [benchmarkConfigOptions, setBenchmarkConfigOptions] = useState<string[]>(["benchmark/configs/example.yaml"]);
  const [benchmarkManualPathEnabled, setBenchmarkManualPathEnabled] = useState(false);

  useEffect(() => {
    let alive = true;
    void (async () => {
      setInitializing(true);
      const [methodsResult, datasetsResult, runsResult, attackConfigResult, benchmarkConfigResult] =
        await Promise.allSettled([
          getQuickAttackMethods(),
          getQuickAttackDatasets(),
          getRuns(),
          getAttackConfigOptions(),
          getBenchmarkConfigOptions()
        ]);

      if (!alive) {
        return;
      }

      if (methodsResult.status === "fulfilled") {
        const methods = (methodsResult.value.methods || []).filter((item) => !!item).sort();
        if (methods.length > 0) {
          setMethodOptions(methods);
          setPayload((prev) => ({
            ...prev,
            quick_attack_methods: (() => {
              const retained = prev.quick_attack_methods.filter((name) => methods.includes(name));
              if (retained.length > 0) {
                return retained;
              }
              return methods.slice(0, Math.min(3, methods.length));
            })()
          }));
        }
      }

      if (datasetsResult.status === "fulfilled") {
        const datasets = datasetsResult.value.datasets || [];
        if (datasets.length > 0) {
          setDatasetOptions(datasets);
          setPayload((prev) => ({
            ...prev,
            quick_dataset_key: datasets.some((item) => item.key === prev.quick_dataset_key)
              ? prev.quick_dataset_key
              : datasets[0].key
          }));
        }
      }

      if (runsResult.status === "fulfilled") {
        const options = runsResult.value.filter((run) => !!run.result_manifest?.trim());
        setManifestSourceRuns(options);
      }

      if (attackConfigResult.status === "fulfilled") {
        const items = [...(attackConfigResult.value.directories || []), ...(attackConfigResult.value.yaml_files || [])]
          .filter((item) => !!item)
          .sort();
        if (items.length > 0) {
          setAttackConfigPathOptions(items);
        }
      }

      if (benchmarkConfigResult.status === "fulfilled") {
        const items = (benchmarkConfigResult.value.yaml_files || []).filter((item) => !!item).sort();
        if (items.length > 0) {
          setBenchmarkConfigOptions(items);
        }
      }

      setInitializing(false);
    })();

    return () => {
      alive = false;
    };
  }, []);

  const isAttackMode = payload.mode === "attack_only" || payload.mode === "full_pipeline";
  const isBenchmarkMode = payload.mode === "benchmark_only" || payload.mode === "full_pipeline";
  const isEvaluateMode = payload.mode === "eval_only" || payload.mode === "full_pipeline";

  const selectedCount = useMemo(() => payload.quick_attack_methods.length, [payload.quick_attack_methods]);
  const selectedDataset = useMemo(
    () => datasetOptions.find((item) => item.key === payload.quick_dataset_key) || null,
    [datasetOptions, payload.quick_dataset_key]
  );
  const selectedManifestSourceRun = useMemo(
    () => manifestSourceRuns.find((run) => run.run_id === manifestSourceRunId) || null,
    [manifestSourceRunId, manifestSourceRuns]
  );
  const benchmarkOptionsAvailable = benchmarkConfigOptions.length > 0;
  const showBenchmarkManualPath = benchmarkManualPathEnabled || !benchmarkOptionsAvailable;
  const benchmarkWillRun =
    payload.mode === "benchmark_only" || (payload.mode === "full_pipeline" && !!payload.benchmark_config_path.trim());
  const benchmarkNeedsStandaloneTarget = isBenchmarkMode && !isAttackMode;
  const stagePreview = useMemo(() => {
    const rows: string[] = [];
    if (isAttackMode) {
      rows.push("attack");
    }
    if (benchmarkWillRun) {
      rows.push("benchmark");
    } else if (isBenchmarkMode) {
      rows.push("benchmark (skipped)");
    }
    if (isEvaluateMode) {
      rows.push("evaluate");
    }
    return rows;
  }, [benchmarkWillRun, isAttackMode, isBenchmarkMode, isEvaluateMode]);
  const previewWarnings = useMemo(() => {
    const hints: string[] = [];
    if (isAttackMode && payload.quick_attack_enabled && !payload.quick_attack_methods.length) {
      hints.push("Select at least one attack method.");
    }
    if (benchmarkWillRun && (!payload.quick_openai_base_url.trim() || !payload.quick_openai_api_key.trim())) {
      hints.push("Benchmark needs target model base_url and api_key.");
    }
    if (
      payload.mode === "eval_only" &&
      !(selectedManifestSourceRun?.result_manifest?.trim() || payload.result_manifest.trim())
    ) {
      hints.push("Eval-only mode requires a manifest.");
    }
    return hints;
  }, [
    benchmarkWillRun,
    isAttackMode,
    payload.mode,
    payload.quick_attack_enabled,
    payload.quick_attack_methods,
    payload.quick_openai_api_key,
    payload.quick_openai_base_url,
    payload.result_manifest,
    selectedManifestSourceRun
  ]);

  function toggleMethod(method: string) {
    setPayload((prev) => {
      const exists = prev.quick_attack_methods.includes(method);
      if (exists) {
        return { ...prev, quick_attack_methods: prev.quick_attack_methods.filter((name) => name !== method) };
      }
      return { ...prev, quick_attack_methods: [...prev.quick_attack_methods, method] };
    });
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    const effectiveResultManifest =
      payload.mode === "eval_only" && selectedManifestSourceRun
        ? selectedManifestSourceRun.result_manifest
        : payload.result_manifest;

    if (isAttackMode) {
      if (payload.quick_attack_enabled) {
        if (!payload.quick_target_model_name.trim()) {
          setError("Model name is required in quick attack mode.");
          return;
        }
        if (!payload.quick_dataset_key.trim()) {
          setError("Dataset is required in quick attack mode.");
          return;
        }
        if (!payload.quick_attack_methods.length) {
          setError("Select at least one attack method.");
          return;
        }
      } else if (!payload.attack_config_dir.trim()) {
        setError("Attack config path is required when quick attack is disabled.");
        return;
      }
    }

    if (payload.mode === "benchmark_only" && !payload.benchmark_config_path.trim()) {
      setError("Benchmark config path is required in benchmark_only mode.");
      return;
    }

    if (benchmarkWillRun) {
      if (!payload.quick_target_model_name.trim()) {
        setError("Target model name is required when benchmark stage is enabled.");
        return;
      }
      if (!payload.quick_openai_base_url.trim() || !payload.quick_openai_api_key.trim()) {
        setError("Target model base_url and api_key are required when benchmark stage is enabled.");
        return;
      }
    }

    if (payload.mode === "eval_only" && !effectiveResultManifest.trim()) {
      setError("Result manifest is required in eval_only mode.");
      return;
    }

    const includeTargetModel = isAttackMode || isBenchmarkMode;
    const includeTargetCreds = isBenchmarkMode || (isAttackMode && payload.quick_attack_enabled);

    const submitPayload: RunCreatePayload = {
      ...payload,
      attack_config_dir: payload.attack_config_dir.trim() || "__AUTO__",
      benchmark_config_path: payload.benchmark_config_path.trim(),
      eval_profile: payload.eval_profile.trim() || "full",
      result_manifest: effectiveResultManifest.trim(),
      results_root: payload.results_root.trim() || "data/attack_results",
      quick_attack_enabled: isAttackMode ? payload.quick_attack_enabled : false,
      quick_openai_base_url: includeTargetCreds ? payload.quick_openai_base_url.trim() : "",
      quick_openai_api_key: includeTargetCreds ? payload.quick_openai_api_key.trim() : "",
      quick_target_model_name: includeTargetModel ? payload.quick_target_model_name.trim() || "gpt-4o-mini" : "gpt-4o-mini",
      quick_attack_methods: isAttackMode ? payload.quick_attack_methods : [],
      quick_dataset_key: isAttackMode ? payload.quick_dataset_key : "teleai_samples_500_500"
    };

    setSubmitting(true);
    try {
      const run = await createRun(submitPayload);
      router.push(`/runs/${run.run_id}`);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : String(err);
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel p-6">
      <div className="mb-5">
        <p className="label">Runs Console</p>
        <h2 className="title-gradient font-headline text-2xl font-semibold">New Run</h2>
        <p className="mt-2 text-sm text-slate-600">
          Choose mode and inputs. Attack/evaluate outputs are isolated by run id on backend.
        </p>
      </div>
      {initializing ? (
        <p aria-live="polite" className="notice mb-4 inline-flex items-center gap-2 text-slate-700">
          <span className="refresh-dot" />
          loading latest config options...
        </p>
      ) : null}

      <form aria-busy={submitting || initializing} onSubmit={onSubmit}>
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
          <div className="space-y-5 xl:col-span-8">
            <article className="section-card">
              <p className="label mb-3">Basic Setup</p>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <label>
                  <span className="label mb-1 block">Run Name (optional)</span>
                  <input
                    className="input"
                    onChange={(event) => setPayload((prev) => ({ ...prev, name: event.target.value }))}
                    placeholder="e.g. gpt4o-mini-nightly"
                    value={payload.name}
                  />
                </label>
                <label>
                  <span className="label mb-1 block">Mode</span>
                  <select
                    className="select"
                    onChange={(event) => {
                      const nextMode = event.target.value as RunMode;
                      setPayload((prev) => ({
                        ...prev,
                        mode: nextMode,
                        quick_attack_enabled:
                          nextMode === "attack_only" || nextMode === "full_pipeline" ? prev.quick_attack_enabled : false
                      }));
                      if (nextMode !== "eval_only") {
                        setManifestSourceRunId("");
                      }
                    }}
                    value={payload.mode}
                  >
                    {runModeOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </article>

            {isAttackMode ? (
              <article className="section-card">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                  <p className="label">Attack Settings</p>
                  <label className="flex items-center gap-2 text-sm text-slate-700">
                    <input
                      checked={payload.quick_attack_enabled}
                      onChange={(event) =>
                        setPayload((prev) => ({
                          ...prev,
                          quick_attack_enabled: event.target.checked,
                          attack_config_dir: event.target.checked ? "__AUTO__" : "configs/gpt-5.4"
                        }))
                      }
                      type="checkbox"
                    />
                    Quick Attack
                  </label>
                </div>

                {payload.quick_attack_enabled ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                      <label>
                        <span className="label mb-1 block">Target Model Name</span>
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
                      <label>
                        <span className="label mb-1 block">Dataset</span>
                        <select
                          className="select"
                          onChange={(event) =>
                            setPayload((prev) => ({
                              ...prev,
                              quick_dataset_key: event.target.value
                            }))
                          }
                          value={payload.quick_dataset_key}
                        >
                          {datasetOptions.map((item) => (
                            <option disabled={!item.exists} key={item.key} value={item.key}>
                              {item.exists ? item.name : `${item.name} (unavailable)`}
                            </option>
                          ))}
                        </select>
                        {selectedDataset ? <p className="mt-1 text-xs text-slate-600">{selectedDataset.description}</p> : null}
                      </label>
                    </div>

                    <details className="rounded-xl border border-slate-200 bg-slate-50/70 p-3">
                      <summary className="cursor-pointer text-sm font-medium text-slate-700">
                        Target API Credentials {benchmarkWillRun ? "(required for benchmark)" : "(optional)"}
                      </summary>
                      <div className="mt-3 space-y-3">
                        <label>
                          <span className="label mb-1 block">OpenAI Base URL</span>
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
                          <span className="label mb-1 block">OpenAI API Key</span>
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

                    <details className="rounded-xl border border-slate-200 bg-slate-50/70 p-3" open={selectedCount === 0}>
                      <summary className="cursor-pointer text-sm font-medium text-slate-700">
                        Attack Methods ({selectedCount} selected / {methodOptions.length})
                      </summary>
                      <div className="mt-3 space-y-3">
                        <div className="flex items-center gap-2">
                          <button
                            className="btn"
                            onClick={() => setPayload((prev) => ({ ...prev, quick_attack_methods: [...methodOptions] }))}
                            type="button"
                          >
                            Select All
                          </button>
                          <button
                            className="btn"
                            onClick={() => setPayload((prev) => ({ ...prev, quick_attack_methods: [] }))}
                            type="button"
                          >
                            Clear
                          </button>
                        </div>
                        <div className="method-grid">
                          {methodOptions.map((method) => {
                            const selected = payload.quick_attack_methods.includes(method);
                            return (
                              <label
                                className={selected ? "method-chip method-chip-active" : "method-chip"}
                                key={method}
                              >
                                <input
                                  checked={selected}
                                  className="sr-only"
                                  onChange={() => toggleMethod(method)}
                                  type="checkbox"
                                />
                                {method}
                              </label>
                            );
                          })}
                        </div>
                      </div>
                    </details>
                  </div>
                ) : (
                  <label>
                    <span className="label mb-1 block">Attack Config Path (directory or .yaml)</span>
                    <input
                      className="input mono"
                      list="attackConfigPathOptions"
                      onChange={(event) => setPayload((prev) => ({ ...prev, attack_config_dir: event.target.value }))}
                      placeholder="configs/gpt-5.4"
                      value={payload.attack_config_dir}
                    />
                    <datalist id="attackConfigPathOptions">
                      {attackConfigPathOptions.map((item) => (
                        <option key={item} value={item} />
                      ))}
                    </datalist>
                    <p className="mt-1 text-xs text-slate-600">
                      Use a directory to run all yaml files, or a single yaml path to run one method.
                    </p>
                  </label>
                )}
              </article>
            ) : null}

            {isBenchmarkMode ? (
              <article className="section-card">
                <p className="label mb-3">Benchmark Settings</p>
                <div className="space-y-3">
                  {showBenchmarkManualPath ? (
                    <label>
                      <span className="label mb-1 block">Benchmark Config Path</span>
                      <input
                        className="input mono"
                        onChange={(event) => setPayload((prev) => ({ ...prev, benchmark_config_path: event.target.value }))}
                        placeholder="benchmark/configs/run/code/run_code_merged_model_only.yaml"
                        value={payload.benchmark_config_path}
                      />
                    </label>
                  ) : (
                    <label>
                      <span className="label mb-1 block">Benchmark Config File</span>
                      <select
                        className="select mono"
                        onChange={(event) => setPayload((prev) => ({ ...prev, benchmark_config_path: event.target.value }))}
                        value={payload.benchmark_config_path}
                      >
                        <option value="">
                          {payload.mode === "benchmark_only" ? "Select benchmark config file" : "Skip benchmark stage"}
                        </option>
                        {benchmarkConfigOptions.map((item) => (
                          <option key={item} value={item}>
                            {item}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}

                  <label className="flex items-center gap-2 text-sm text-slate-700">
                    <input
                      checked={benchmarkManualPathEnabled}
                      disabled={!benchmarkOptionsAvailable}
                      onChange={(event) => {
                        const checked = event.target.checked;
                        setBenchmarkManualPathEnabled(checked);
                        if (!checked && !benchmarkConfigOptions.includes(payload.benchmark_config_path)) {
                          setPayload((prev) => ({ ...prev, benchmark_config_path: "" }));
                        }
                      }}
                      type="checkbox"
                    />
                    Manual benchmark config path
                  </label>
                </div>

                {benchmarkNeedsStandaloneTarget ? (
                  <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
                    <label>
                      <span className="label mb-1 block">Target Model Name</span>
                      <input
                        className="input"
                        onChange={(event) => setPayload((prev) => ({ ...prev, quick_target_model_name: event.target.value }))}
                        placeholder="gpt-4o-mini"
                        value={payload.quick_target_model_name}
                      />
                    </label>
                    <label>
                      <span className="label mb-1 block">Target OpenAI Base URL</span>
                      <input
                        className="input mono"
                        onChange={(event) => setPayload((prev) => ({ ...prev, quick_openai_base_url: event.target.value }))}
                        placeholder="https://api.openai.com/v1"
                        value={payload.quick_openai_base_url}
                      />
                    </label>
                    <label className="md:col-span-2">
                      <span className="label mb-1 block">Target OpenAI API Key</span>
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
                  <p className="mt-4 rounded-xl border border-slate-200 bg-slate-50/70 p-3 text-sm text-slate-700">
                    Benchmark will reuse target model settings from Attack section in full pipeline mode.
                  </p>
                )}
                <p className="mt-2 text-xs text-slate-600">
                  Runtime config is generated from template; top-level benchmark model is auto-bound to target model.
                </p>
              </article>
            ) : null}

            {isEvaluateMode ? (
              <article className="section-card">
                <p className="label mb-3">Evaluate Settings</p>
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <label>
                    <span className="label mb-1 block">Eval Profile</span>
                    <select
                      className="select"
                      onChange={(event) => setPayload((prev) => ({ ...prev, eval_profile: event.target.value }))}
                      value={payload.eval_profile}
                    >
                      <option value="full">full</option>
                      <option value="smoke">smoke</option>
                    </select>
                  </label>
                  <label>
                    <span className="label mb-1 block">Results Root</span>
                    <input
                      className="input mono"
                      onChange={(event) => setPayload((prev) => ({ ...prev, results_root: event.target.value }))}
                      placeholder="data/attack_results"
                      value={payload.results_root}
                    />
                  </label>
                </div>

                {payload.mode === "eval_only" ? (
                  <div className="mt-4 space-y-4">
                    <label>
                      <span className="label mb-1 block">Use Existing Run Manifest (optional)</span>
                      <select
                        className="select"
                        onChange={(event) => setManifestSourceRunId(event.target.value)}
                        value={manifestSourceRunId}
                      >
                        <option value="">Manual manifest path</option>
                        {manifestSourceRuns.map((item) => (
                          <option key={item.run_id} value={item.run_id}>
                            {item.name} ({item.run_id.slice(0, 8)})
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      <span className="label mb-1 block">Result Manifest Path</span>
                      <input
                        className="input mono"
                        disabled={!!selectedManifestSourceRun}
                        onChange={(event) => setPayload((prev) => ({ ...prev, result_manifest: event.target.value }))}
                        placeholder="data/attack_results/runs/<run_id>/manifests/<name>.txt"
                        value={selectedManifestSourceRun ? selectedManifestSourceRun.result_manifest : payload.result_manifest}
                      />
                    </label>
                  </div>
                ) : (
                  <label className="mt-4 block">
                    <span className="label mb-1 block">Result Manifest Path (optional)</span>
                    <input
                      className="input mono"
                      onChange={(event) => setPayload((prev) => ({ ...prev, result_manifest: event.target.value }))}
                      placeholder="Leave empty to use this run's attack outputs"
                      value={payload.result_manifest}
                    />
                  </label>
                )}
              </article>
            ) : null}

            {error ? (
              <p aria-live="assertive" className="notice notice-error" role="alert">
                {error}
              </p>
            ) : null}
            <div className="flex flex-wrap items-center gap-2">
              <button className={submitting ? "btn btn-primary btn-busy" : "btn btn-primary"} disabled={submitting || initializing} type="submit">
                {submitting ? "Submitting..." : initializing ? "Preparing..." : modeSubmitLabel(payload.mode)}
              </button>
              <button
                className="btn"
                onClick={() => {
                  setPayload(defaultPayload);
                  setManifestSourceRunId("");
                  setBenchmarkManualPathEnabled(false);
                  setError("");
                }}
                type="button"
              >
                Reset
              </button>
            </div>
          </div>

          <aside className="space-y-4 xl:col-span-4 xl:sticky xl:top-6 xl:self-start">
            <article className="stat-card">
              <p className="label mb-2">Run Preview</p>
              <dl className="space-y-2 text-sm text-slate-700">
                <div>
                  <dt className="label">Mode</dt>
                  <dd>{payload.mode}</dd>
                </div>
                <div>
                  <dt className="label">Stages</dt>
                  <dd className="mono text-xs">{stagePreview.join(" -> ") || "-"}</dd>
                </div>
                <div>
                  <dt className="label">Target Model</dt>
                  <dd>{payload.quick_target_model_name || "-"}</dd>
                </div>
                <div>
                  <dt className="label">Attack Methods</dt>
                  <dd>{isAttackMode && payload.quick_attack_enabled ? selectedCount : 0}</dd>
                </div>
                <div>
                  <dt className="label">Benchmark Config</dt>
                  <dd className="mono text-xs">{payload.benchmark_config_path || "-"}</dd>
                </div>
              </dl>
            </article>

            <article className="stat-card">
              <p className="label mb-2">Checklist</p>
              {previewWarnings.length ? (
                <div className="notice notice-warn">
                  <ul className="space-y-1 text-sm">
                    {previewWarnings.map((item) => (
                      <li key={item}>- {item}</li>
                    ))}
                  </ul>
                </div>
              ) : (
                <p className="notice notice-good text-sm">Form looks good. Ready to start.</p>
              )}
              <p className="mt-3 text-xs text-slate-600">
                Artifacts and intermediate outputs are isolated by run id, avoiding cross-run pollution.
              </p>
            </article>
          </aside>
        </div>
      </form>
    </section>
  );
}
