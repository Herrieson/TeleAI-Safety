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
    void (async () => {
      try {
        const data = await getQuickAttackMethods();
        const methods = (data.methods || []).filter((item) => !!item).sort();
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
      } catch {
        // keep fallback method options
      }

      try {
        const data = await getQuickAttackDatasets();
        const datasets = data.datasets || [];
        if (datasets.length > 0) {
          setDatasetOptions(datasets);
          setPayload((prev) => ({
            ...prev,
            quick_dataset_key: datasets.some((item) => item.key === prev.quick_dataset_key)
              ? prev.quick_dataset_key
              : datasets[0].key
          }));
        }
      } catch {
        // keep fallback dataset options
      }

      try {
        const runs = await getRuns();
        const options = runs.filter((run) => !!run.result_manifest?.trim());
        setManifestSourceRuns(options);
      } catch {
        // source run selector remains empty
      }

      try {
        const data = await getAttackConfigOptions();
        const items = [...(data.directories || []), ...(data.yaml_files || [])]
          .filter((item) => !!item)
          .sort();
        if (items.length > 0) {
          setAttackConfigPathOptions(items);
        }
      } catch {
        // keep fallback options
      }

      try {
        const data = await getBenchmarkConfigOptions();
        const items = (data.yaml_files || []).filter((item) => !!item).sort();
        if (items.length > 0) {
          setBenchmarkConfigOptions(items);
        }
      } catch {
        // keep fallback options
      }
    })();
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
        <h2 className="font-headline text-2xl font-semibold">New Run</h2>
        <p className="mt-2 text-sm text-slate-600">
          Choose mode and inputs. Attack/evaluate outputs are isolated by run id on backend.
        </p>
      </div>

      <form className="space-y-5" onSubmit={onSubmit}>
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

        {isAttackMode ? (
          <article className="rounded-xl border border-slate-200 bg-white/80 p-4">
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

                <label>
                  <span className="label mb-1 block">OpenAI Base URL (optional)</span>
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
                  <span className="label mb-1 block">OpenAI API Key (optional)</span>
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
                <p className="text-xs text-slate-600">
                  {isBenchmarkMode
                    ? "If benchmark stage is enabled, target base_url/api_key should be provided for benchmark runtime patching."
                    : "If backend internal LLM credentials are configured, these frontend fields can be left empty."}
                </p>

                <fieldset>
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <p className="label">
                      Attack Methods ({selectedCount} selected / {methodOptions.length} available)
                    </p>
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
                  </div>
                  <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
                    {methodOptions.map((method) => {
                      const selected = payload.quick_attack_methods.includes(method);
                      return (
                        <label
                          className={`cursor-pointer rounded-lg border px-3 py-2 text-center text-sm font-medium ${
                            selected
                              ? "border-blue-500 bg-blue-50 text-blue-700"
                              : "border-slate-300 bg-white text-slate-700"
                          }`}
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
                </fieldset>
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
          <article className="rounded-xl border border-slate-200 bg-white/80 p-4">
            <p className="label mb-2">Benchmark Settings</p>
            <div className="space-y-3">
              {showBenchmarkManualPath ? (
                <label>
                  <span className="label mb-1 block">Benchmark Config Path</span>
                  <input
                    className="input mono"
                    onChange={(event) => setPayload((prev) => ({ ...prev, benchmark_config_path: event.target.value }))}
                    placeholder="benchmark/configs/example.yaml"
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
              {!benchmarkOptionsAvailable ? (
                <p className="text-xs text-amber-700">No benchmark config files found under benchmark/configs.</p>
              ) : null}
            </div>
            <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
              <label>
                <span className="label mb-1 block">Target Model Name (for benchmark)</span>
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
            </div>
            <label className="mt-4 block">
              <span className="label mb-1 block">Target OpenAI API Key</span>
              <input
                className="input mono"
                onChange={(event) => setPayload((prev) => ({ ...prev, quick_openai_api_key: event.target.value }))}
                placeholder="sk-..."
                type="password"
                value={payload.quick_openai_api_key}
              />
            </label>
            <p className="mt-2 text-xs text-slate-600">
              Benchmark will auto-generate runtime config from template and bind top-level model to this target model.
            </p>
            {payload.mode === "full_pipeline" ? (
              <p className="mt-2 text-xs text-slate-600">Leave empty to skip benchmark stage in full pipeline.</p>
            ) : null}
          </article>
        ) : null}

        {isEvaluateMode ? (
          <article className="rounded-xl border border-slate-200 bg-white/80 p-4">
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

        {error ? <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p> : null}
        <div className="flex items-center gap-2">
          <button className="btn btn-primary" disabled={submitting} type="submit">
            {submitting ? "Submitting..." : modeSubmitLabel(payload.mode)}
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
      </form>
    </section>
  );
}
