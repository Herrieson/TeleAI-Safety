"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ApiError,
  createRun,
  getBenchmarkConfigOptions,
  getManagedTargetModels,
  getQuickAttackMethods,
  getRuns
} from "@/lib/api";
import { useI18n } from "@/components/common/LocaleProvider";
import { NewRunTour } from "@/components/runs/new/NewRunTour";
import { formatStageName } from "@/lib/i18n";
import { AdvancedModeForm } from "@/components/runs/new/AdvancedModeForm";
import { ManagedModeForm } from "@/components/runs/new/ManagedModeForm";
import { RunModeSwitcher } from "@/components/runs/new/RunModeSwitcher";
import { SimpleModeForm } from "@/components/runs/new/SimpleModeForm";
import { DEFAULT_QUICK_DATASET_KEY, defaultRunPayload, fallbackMethodOptions, runModeOptions, type NewRunViewMode } from "@/lib/newRunConfig";
import { getNewRunText } from "@/lib/newRunText";
import type { ManagedModePolicy, ManagedTargetModel, Run, RunCreatePayload } from "@/lib/types";

export default function NewRunPage() {
  const { locale } = useI18n();
  const text = getNewRunText(locale);
  const router = useRouter();

  const [viewMode, setViewMode] = useState<NewRunViewMode>("simple");
  const [payload, setPayload] = useState<RunCreatePayload>(defaultRunPayload);
  const [submitting, setSubmitting] = useState(false);
  const [initializing, setInitializing] = useState(true);
  const [error, setError] = useState("");
  const [methodOptions, setMethodOptions] = useState<string[]>(fallbackMethodOptions);
  const [manifestSourceRuns, setManifestSourceRuns] = useState<Run[]>([]);
  const [manifestSourceRunId, setManifestSourceRunId] = useState("");
  const [benchmarkConfigOptions, setBenchmarkConfigOptions] = useState<string[]>(["benchmark/configs/run.yaml"]);
  const [managedTargetModels, setManagedTargetModels] = useState<ManagedTargetModel[]>([]);
  const [managedPolicy, setManagedPolicy] = useState<ManagedModePolicy | null>(null);
  const [tourOpen, setTourOpen] = useState(false);
  const [tourCompleted, setTourCompleted] = useState(false);

  const tourSteps = useMemo(
    () => [
      {
        viewMode: "simple" as NewRunViewMode,
        target: "new-run-view-mode",
        title: text.tourStepViewModeTitle,
        description: text.tourStepViewModeDesc
      },
      {
        viewMode: "simple" as NewRunViewMode,
        target: "simple-main-form",
        title: text.tourStepSimpleTitle,
        description: text.tourStepSimpleDesc
      },
      {
        viewMode: "managed" as NewRunViewMode,
        target: "managed-main-form",
        title: text.tourStepManagedTitle,
        description: text.tourStepManagedDesc
      },
      {
        viewMode: "advanced" as NewRunViewMode,
        target: "advanced-run-mode",
        title: text.tourStepAdvancedTitle,
        description: text.tourStepAdvancedDesc
      },
      {
        viewMode: "advanced" as NewRunViewMode,
        target: "advanced-attack-methods",
        title: text.tourStepMethodsTitle,
        description: text.tourStepMethodsDesc
      },
      {
        viewMode: "advanced" as NewRunViewMode,
        target: "advanced-submit",
        title: text.tourStepSubmitTitle,
        description: text.tourStepSubmitDesc
      }
    ],
    [text]
  );

  useEffect(() => {
    let alive = true;

    void (async () => {
      setInitializing(true);
      const [methodsResult, runsResult, benchmarkConfigResult, managedModelsResult] = await Promise.allSettled([
        getQuickAttackMethods(),
        getRuns(),
        getBenchmarkConfigOptions(),
        getManagedTargetModels()
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

      if (runsResult.status === "fulfilled") {
        setManifestSourceRuns((runsResult.value || []).filter((run) => !!run.result_manifest?.trim()));
      }

      if (benchmarkConfigResult.status === "fulfilled") {
        const items = (benchmarkConfigResult.value.yaml_files || []).filter((item) => !!item).sort();
        if (items.length > 0) {
          setBenchmarkConfigOptions(items);
        }
      }

      if (managedModelsResult.status === "fulfilled") {
        const models = (managedModelsResult.value.models || []).filter((item) => !!item.id && !!item.target_model_name);
        setManagedTargetModels(models);
        setManagedPolicy(managedModelsResult.value.policy || null);
        if (models.length > 0) {
          setPayload((prev) => ({
            ...prev,
            managed_target_model_id:
              prev.managed_target_model_id && models.some((item) => item.id === prev.managed_target_model_id)
                ? prev.managed_target_model_id
                : models[0].id,
            quick_target_model_name: prev.quick_target_model_name || models[0].target_model_name
          }));
        }
      }

      setInitializing(false);
    })();

    return () => {
      alive = false;
    };
  }, []);

  const isManagedView = viewMode === "managed";
  const isSimpleView = viewMode === "simple";
  const isAttackMode = payload.mode === "attack_only" || payload.mode === "full_pipeline";
  const isBenchmarkMode = payload.mode === "benchmark_only" || payload.mode === "full_pipeline";
  const isEvaluateMode = payload.mode === "eval_only" || payload.mode === "full_pipeline";

  const selectedCount = useMemo(() => payload.quick_attack_methods.length, [payload.quick_attack_methods]);
  const selectedManagedModel = useMemo(
    () => managedTargetModels.find((item) => item.id === payload.managed_target_model_id) || null,
    [managedTargetModels, payload.managed_target_model_id]
  );
  const managedInviteCodeRequired = !!managedPolicy?.invite_code_required;
  const selectedManifestSourceRun = useMemo(
    () => manifestSourceRuns.find((run) => run.run_id === manifestSourceRunId) || null,
    [manifestSourceRunId, manifestSourceRuns]
  );
  const benchmarkWillRun = isBenchmarkMode;
  const benchmarkNeedsStandaloneTarget = isBenchmarkMode && !isAttackMode;

  useEffect(() => {
    if (isBenchmarkMode && benchmarkConfigOptions.length && payload.benchmark_config_path !== benchmarkConfigOptions[0]) {
      setPayload((prev) => ({
        ...prev,
        benchmark_config_path: benchmarkConfigOptions[0]
      }));
    }
  }, [benchmarkConfigOptions, isBenchmarkMode, payload.benchmark_config_path]);

  useEffect(() => {
    if (payload.mode === "eval_only" && !manifestSourceRunId && manifestSourceRuns.length) {
      setManifestSourceRunId(manifestSourceRuns[0].run_id);
    }
  }, [manifestSourceRunId, manifestSourceRuns, payload.mode]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    setTourCompleted(window.localStorage.getItem("teleai:new-run-tour:completed") === "1");
  }, []);

  const stagePreview = useMemo(() => {
    const rows: string[] = [];
    if (isAttackMode) {
      rows.push(formatStageName("attack", locale));
    }
    if (benchmarkWillRun) {
      rows.push(formatStageName("benchmark", locale));
    } else if (isBenchmarkMode) {
      rows.push(locale === "zh" ? `${formatStageName("benchmark", locale)}（跳过）` : `${formatStageName("benchmark", locale)} (skipped)`);
    }
    if (isEvaluateMode) {
      rows.push(formatStageName("evaluate", locale));
    }
    return rows;
  }, [benchmarkWillRun, isAttackMode, isBenchmarkMode, isEvaluateMode, locale]);

  const autoDatasetKey = DEFAULT_QUICK_DATASET_KEY;
  const autoBenchmarkConfigPath = useMemo(
    () => benchmarkConfigOptions[0] || payload.benchmark_config_path || "benchmark/configs/run.yaml",
    [benchmarkConfigOptions, payload.benchmark_config_path]
  );
  const autoMethodList = useMemo(() => (methodOptions.length ? methodOptions : fallbackMethodOptions), [methodOptions]);
  const autoStageSummary = useMemo(
    () => [formatStageName("attack", locale), formatStageName("benchmark", locale), formatStageName("evaluate", locale)].join(" -> "),
    [locale]
  );
  const previewWarnings = useMemo(() => {
    const hints: string[] = [];
    if (isAttackMode && !payload.quick_attack_methods.length) {
      hints.push(text.warnSelectMethod);
    }
    if (benchmarkWillRun && (!payload.quick_openai_base_url.trim() || !payload.quick_openai_api_key.trim())) {
      hints.push(text.warnBenchmarkCreds);
    }
    if (payload.mode === "eval_only" && !(selectedManifestSourceRun?.result_manifest?.trim() || payload.result_manifest.trim())) {
      hints.push(text.warnEvalManifest);
    }
    return hints;
  }, [
    benchmarkWillRun,
    isAttackMode,
    payload.mode,
    payload.quick_attack_methods,
    payload.quick_openai_api_key,
    payload.quick_openai_base_url,
    payload.result_manifest,
    selectedManifestSourceRun,
    text
  ]);

  function handleViewModeChange(nextMode: NewRunViewMode) {
    setViewMode(nextMode);
    setError("");

    if (nextMode === "managed") {
      setPayload((prev) => {
        const hasCurrent = prev.managed_target_model_id && managedTargetModels.some((item) => item.id === prev.managed_target_model_id);
        const first = managedTargetModels[0] || null;
        const nextModel = hasCurrent
          ? managedTargetModels.find((item) => item.id === prev.managed_target_model_id) || first
          : first;
        return {
          ...prev,
          managed_target_model_id: nextModel?.id || "",
          quick_target_model_name: nextModel?.target_model_name || prev.quick_target_model_name
        };
      });
      return;
    }

    setPayload((prev) => ({ ...prev, managed_target_model_id: "", managed_access_code: "" }));
  }

  function toggleMethod(method: string) {
    setPayload((prev) => {
      const exists = prev.quick_attack_methods.includes(method);
      if (exists) {
        return { ...prev, quick_attack_methods: prev.quick_attack_methods.filter((name) => name !== method) };
      }
      return { ...prev, quick_attack_methods: [...prev.quick_attack_methods, method] };
    });
  }

  function resetSimpleMode() {
    setPayload(defaultRunPayload);
    setManifestSourceRunId("");
    setViewMode("simple");
    setError("");
  }

  function resetManagedMode() {
    const first = managedTargetModels[0] || null;
    setPayload({
      ...defaultRunPayload,
      managed_target_model_id: first?.id || "",
      quick_target_model_name: first?.target_model_name || ""
    });
    setManifestSourceRunId("");
    setViewMode("managed");
    setError("");
  }

  function resetAdvancedMode() {
    setPayload(defaultRunPayload);
    setManifestSourceRunId("");
    setViewMode("advanced");
    setError("");
  }

  function startTour() {
    if (initializing) {
      return;
    }
    setViewMode("simple");
    setTourOpen(true);
  }

  function handleTourClose(completed: boolean) {
    setTourOpen(false);
    if (completed && typeof window !== "undefined") {
      window.localStorage.setItem("teleai:new-run-tour:completed", "1");
      setTourCompleted(true);
    }
  }

  function handleTourStepChange(index: number) {
    const nextViewMode = tourSteps[index]?.viewMode;
    if (nextViewMode && nextViewMode !== viewMode) {
      setViewMode(nextViewMode);
    }
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    if (isManagedView) {
      const managedId = payload.managed_target_model_id?.trim() || selectedManagedModel?.id || "";
      if (!managedId) {
        setError(text.errManagedModel);
        return;
      }

      const modelName = selectedManagedModel?.target_model_name || payload.quick_target_model_name || "gpt-4o-mini";
      const submitPayload: RunCreatePayload = {
        ...payload,
        mode: "full_pipeline",
        attack_config_dir: "__AUTO__",
        benchmark_config_path: autoBenchmarkConfigPath,
        eval_profile: "full",
        result_manifest: "",
        results_root: payload.results_root.trim() || "data/attack_results",
        quick_attack_enabled: true,
        quick_openai_base_url: "",
        quick_openai_api_key: "",
        quick_target_model_name: modelName,
        quick_attack_methods: [...autoMethodList],
        quick_dataset_key: autoDatasetKey,
        managed_target_model_id: managedId,
        managed_access_code: (payload.managed_access_code || "").trim()
      };

      setSubmitting(true);
      try {
        const run = await createRun(submitPayload);
        router.push(`/runs/${run.run_id}`);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : String(err));
      } finally {
        setSubmitting(false);
      }
      return;
    }

    if (isSimpleView) {
      if (!payload.quick_target_model_name.trim()) {
        setError(text.errSimpleTargetModel);
        return;
      }
      if (!payload.quick_openai_base_url.trim() || !payload.quick_openai_api_key.trim()) {
        setError(text.errSimpleCreds);
        return;
      }

      const submitPayload: RunCreatePayload = {
        ...payload,
        mode: "full_pipeline",
        attack_config_dir: "__AUTO__",
        benchmark_config_path: autoBenchmarkConfigPath,
        eval_profile: "full",
        result_manifest: "",
        results_root: payload.results_root.trim() || "data/attack_results",
        quick_attack_enabled: true,
        quick_openai_base_url: payload.quick_openai_base_url.trim(),
        quick_openai_api_key: payload.quick_openai_api_key.trim(),
        quick_target_model_name: payload.quick_target_model_name.trim(),
        quick_attack_methods: [...autoMethodList],
        quick_dataset_key: autoDatasetKey,
        managed_target_model_id: "",
        managed_access_code: ""
      };

      setSubmitting(true);
      try {
        const run = await createRun(submitPayload);
        router.push(`/runs/${run.run_id}`);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : String(err));
      } finally {
        setSubmitting(false);
      }
      return;
    }

    const effectiveResultManifest =
      payload.mode === "eval_only" && selectedManifestSourceRun ? selectedManifestSourceRun.result_manifest : payload.result_manifest;

    if (isAttackMode) {
      if (!payload.quick_target_model_name.trim()) {
        setError(text.errModelNameQuick);
        return;
      }
      if (!payload.quick_attack_methods.length) {
        setError(text.warnSelectMethod);
        return;
      }
    }

    if (benchmarkWillRun) {
      if (!payload.quick_target_model_name.trim()) {
        setError(text.errTargetModelBenchmark);
        return;
      }
      if (!payload.quick_openai_base_url.trim() || !payload.quick_openai_api_key.trim()) {
        setError(text.errTargetCredsBenchmark);
        return;
      }
    }

    if (payload.mode === "eval_only" && !effectiveResultManifest.trim()) {
      setError(text.errResultManifest);
      return;
    }

    const includeTargetModel = isAttackMode || isBenchmarkMode;
    const includeTargetCreds = isBenchmarkMode || isAttackMode;

    const submitPayload: RunCreatePayload = {
      ...payload,
      attack_config_dir: isAttackMode ? "__AUTO__" : payload.attack_config_dir.trim() || "__AUTO__",
      benchmark_config_path: isBenchmarkMode ? autoBenchmarkConfigPath : "",
      eval_profile: payload.eval_profile.trim() || "full",
      result_manifest: effectiveResultManifest.trim(),
      results_root: payload.results_root.trim() || "data/attack_results",
      quick_attack_enabled: isAttackMode,
      quick_openai_base_url: includeTargetCreds ? payload.quick_openai_base_url.trim() : "",
      quick_openai_api_key: includeTargetCreds ? payload.quick_openai_api_key.trim() : "",
      quick_target_model_name: includeTargetModel ? payload.quick_target_model_name.trim() || "gpt-4o-mini" : "gpt-4o-mini",
      quick_attack_methods: isAttackMode ? payload.quick_attack_methods : [],
      quick_dataset_key: isAttackMode ? autoDatasetKey : DEFAULT_QUICK_DATASET_KEY,
      managed_target_model_id: "",
      managed_access_code: ""
    };

    setSubmitting(true);
    try {
      const run = await createRun(submitPayload);
      router.push(`/runs/${run.run_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel p-6">
      <div className="page-hero mb-5">
        <div>
          <p className="label">{text.runsConsole}</p>
          <h2 className="title-gradient font-headline text-2xl font-semibold">{text.newRun}</h2>
        </div>
        <div className="empty-state-actions">
          <button className="btn hidden md:inline-flex" disabled={initializing} onClick={startTour} type="button">
            {tourCompleted ? text.restartTour : text.startTour}
          </button>
        </div>
      </div>

      {initializing ? (
        <p aria-live="polite" className="notice mb-4 inline-flex items-center gap-2 text-slate-700">
          <span className="refresh-dot" />
          {text.loadingConfig}
        </p>
      ) : null}

      <div className="notice notice-warn mb-5 space-y-3 md:hidden">
        <div>
          <p className="font-headline text-sm font-semibold text-amber-100">{text.mobileTitle}</p>
          <p className="mt-1 text-sm text-amber-50/90">{text.mobileDesc}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link className="btn btn-primary" href="/runs">
            {text.mobileOpenRuns}
          </Link>
        </div>
      </div>

      <div className="hidden md:block">
        <div data-tour="new-run-view-mode">
          <RunModeSwitcher
            labels={{ advanced: text.advancedMode, managed: text.managedMode, simple: text.simpleMode }}
            mode={viewMode}
            onChange={handleViewModeChange}
          />
        </div>

        <form aria-busy={submitting || initializing} onSubmit={onSubmit}>
          {isManagedView ? (
            <ManagedModeForm
              autoStageSummary={autoStageSummary}
              error={error}
              initializing={initializing}
              managedInviteCodeRequired={managedInviteCodeRequired}
              managedPolicy={managedPolicy}
              managedTargetModels={managedTargetModels}
              onReset={resetManagedMode}
              payload={payload}
              selectedManagedModel={selectedManagedModel}
              setPayload={setPayload}
              submitting={submitting}
              text={text}
            />
          ) : null}

          {isSimpleView ? (
            <SimpleModeForm
              autoStageSummary={autoStageSummary}
              error={error}
              initializing={initializing}
              onReset={resetSimpleMode}
              payload={payload}
              setPayload={setPayload}
              submitting={submitting}
              text={text}
            />
          ) : null}

          {!isManagedView && !isSimpleView ? (
            <AdvancedModeForm
              benchmarkNeedsStandaloneTarget={benchmarkNeedsStandaloneTarget}
              benchmarkWillRun={benchmarkWillRun}
              error={error}
              initializing={initializing}
              isAttackMode={isAttackMode}
              isBenchmarkMode={isBenchmarkMode}
              isEvaluateMode={isEvaluateMode}
              locale={locale}
              manifestSourceRunId={manifestSourceRunId}
              manifestSourceRuns={manifestSourceRuns}
              methodOptions={methodOptions}
              onReset={resetAdvancedMode}
              onToggleMethod={toggleMethod}
              payload={payload}
              previewWarnings={previewWarnings}
              runModeOptions={runModeOptions}
              selectedCount={selectedCount}
              selectedManifestSourceRun={selectedManifestSourceRun}
              setManifestSourceRunId={setManifestSourceRunId}
              setPayload={setPayload}
              stagePreview={stagePreview}
              submitting={submitting}
              text={text}
            />
          ) : null}
        </form>
      </div>

      <NewRunTour
        layoutKey={viewMode}
        labels={{
          finish: text.tourFinish,
          next: text.tourNext,
          previous: text.tourPrevious,
          skip: text.tourSkip,
          step: text.tourStep,
          title: text.tourTitle
        }}
        onClose={handleTourClose}
        onStepChange={handleTourStepChange}
        open={tourOpen}
        steps={tourSteps}
      />
    </section>
  );
}
