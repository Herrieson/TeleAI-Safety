"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ApiError,
  getAttackConfigOptions,
  getBenchmarkConfigOptions,
  createRun,
  getManagedTargetModels,
  getQuickAttackDatasets,
  getQuickAttackMethods,
  getRuns
} from "@/lib/api";
import { useI18n } from "@/components/common/LocaleProvider";
import { formatRunMode, formatStageName } from "@/lib/i18n";
import { getAttackMethodInfo } from "@/lib/attackMethodInfo";
import type { ManagedModePolicy, ManagedTargetModel, QuickAttackDataset, Run, RunCreatePayload, RunMode } from "@/lib/types";

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
  quick_target_model_name: "",
  quick_openai_base_url: "",
  quick_openai_api_key: "",
  quick_attack_methods: ["pair", "cipher", "rene"],
  quick_dataset_key: "teleai_samples_500_500",
  managed_target_model_id: "",
  managed_access_code: ""
};

const runModeOptions: RunMode[] = ["attack_only", "eval_only", "full_pipeline", "benchmark_only"];

function modeSubmitLabel(mode: RunMode, locale: "zh" | "en"): string {
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

export default function NewRunPage() {
  const { locale } = useI18n();
  const text =
    locale === "zh"
      ? {
          runsConsole: "运行控制台",
          newRun: "新建任务",
          pageDesc: "选择模式和输入项。攻击/评估输出会按 run id 在后端隔离。",
          missionBuilder: "任务编排",
          pipelineComposer: "流水线编辑器",
          ready: "就绪",
          loadingConfig: "正在加载最新配置选项...",
          basicSetup: "基础设置",
          runNameOptional: "任务名称（可选）",
          mode: "模式",
          attackSettings: "攻击设置",
          quickAttack: "快速攻击",
          targetModelName: "目标模型名称",
          dataset: "数据集",
          unavailable: "不可用",
          targetApiCreds: "目标 API 凭证",
          requiredForBenchmark: "（基准测试必填）",
          optional: "（可选）",
          openaiBaseUrl: "OpenAI Base URL",
          openaiApiKey: "OpenAI API Key",
          attackMethods: "攻击方法",
          selected: "已选",
          selectAll: "全选",
          clear: "清空",
          methodIntro: "简介",
          methodPaper: "论文",
          methodRepo: "源码",
          methodNoRef: "暂无公开链接",
          simpleMode: "简洁模式",
          managedMode: "平台托管模式",
          advancedMode: "高级模式",
          simpleModeTitle: "一键完整测试（默认）",
          simpleModeDesc: "需填写目标模型名称和 API 凭证，系统将自动执行攻击 + 基准测试 + 评估完整流程。",
          managedModeTitle: "平台托管模型测试",
          managedModeDesc: "从平台托管模型列表中选择目标，无需填写 Base URL / API Key，系统使用托管资源执行完整测试流程。",
          managedTargetModel: "托管被测模型",
          managedSelectPlaceholder: "请选择托管模型",
          managedNoModels: "当前暂无可用托管模型，请联系管理员配置。",
          managedPolicy: "资源限制",
          managedPolicyHint: (global: number, perIp: number, cooldown: number) =>
            `全局并发上限 ${global}，单客户端并发上限 ${perIp}，同一客户端提交冷却 ${cooldown} 秒。`,
          managedAccessCode: "邀请码",
          managedAccessCodeHint: "管理员白名单之外的用户需输入邀请码。",
          errManagedModel: "请选择托管被测模型。",
          simpleAutoPlanTitle: "自动测试计划",
          simpleAutoMode: "运行模式",
          simpleAutoStages: "执行阶段",
          simpleAutoDataset: "数据集",
          simpleAutoMethods: "攻击方法",
          simpleAutoBenchmark: "基准配置",
          simpleAutoEval: "评估配置",
          simpleSubmit: "开始自动完整测试",
          errSimpleTargetModel: "请先填写目标模型名称。",
          errSimpleCreds: "请先填写 API Base URL 和 API Key。",
          attackConfigPath: "攻击配置路径（目录或 .yaml）",
          attackConfigHelp: "目录会运行其中所有 yaml；单个 yaml 路径只运行一个方法。",
          benchmarkSettings: "基准测试设置",
          benchmarkConfigPath: "基准测试配置路径",
          benchmarkConfigFile: "基准测试配置文件",
          selectBenchmarkConfigFile: "选择基准测试配置文件",
          skipBenchmarkStage: "跳过基准测试阶段",
          manualBenchmarkConfigPath: "手动输入基准测试配置路径",
          targetOpenaiBaseUrl: "目标 OpenAI Base URL",
          targetOpenaiApiKey: "目标 OpenAI API Key",
          benchmarkReuseHint: "完整流水线模式下，基准测试将复用攻击部分的目标模型设置。",
          runtimeConfigHint: "运行时配置由模板生成；benchmark 顶层模型会自动绑定到目标模型。",
          evaluateSettings: "评估设置",
          evalProfile: "评估配置",
          resultsRoot: "结果根目录",
          useExistingRunManifest: "使用已有任务的清单（可选）",
          manualManifestPath: "手动填写清单路径",
          resultManifestPath: "结果清单路径",
          resultManifestPathOptional: "结果清单路径（可选）",
          leaveEmptyManifest: "留空则使用本次任务的攻击输出",
          submitting: "提交中...",
          preparing: "准备中...",
          reset: "重置",
          runPreview: "任务预览",
          stages: "阶段",
          targetModel: "目标模型",
          attackMethodsCount: "攻击方法",
          benchmarkConfig: "基准测试配置",
          checklist: "检查清单",
          formLooksGood: "表单检查通过，可以启动。",
          isolationHint: "产物和中间输出按 run id 隔离，避免跨任务污染。",
          warnSelectMethod: "请至少选择一个攻击方法。",
          warnBenchmarkCreds: "执行基准测试需要目标模型 base_url 和 api_key。",
          warnEvalManifest: "仅评估模式需要提供清单。",
          errModelNameQuick: "快速攻击模式下必须填写模型名称。",
          errDatasetQuick: "快速攻击模式下必须选择数据集。",
          errAttackConfig: "关闭快速攻击时必须填写攻击配置路径。",
          errBenchmarkConfig: "benchmark_only 模式必须填写基准测试配置路径。",
          errTargetModelBenchmark: "启用 benchmark 阶段时必须填写目标模型名称。",
          errTargetCredsBenchmark: "启用 benchmark 阶段时必须填写目标模型 base_url 和 api_key。",
          errResultManifest: "eval_only 模式必须填写结果清单。"
        }
      : {
          runsConsole: "Runs Console",
          newRun: "New Run",
          pageDesc: "Choose mode and inputs. Attack/evaluate outputs are isolated by run id on backend.",
          missionBuilder: "Mission Builder",
          pipelineComposer: "Pipeline Composer",
          ready: "Ready",
          loadingConfig: "loading latest config options...",
          basicSetup: "Basic Setup",
          runNameOptional: "Run Name (optional)",
          mode: "Mode",
          attackSettings: "Attack Settings",
          quickAttack: "Quick Attack",
          targetModelName: "Target Model Name",
          dataset: "Dataset",
          unavailable: "unavailable",
          targetApiCreds: "Target API Credentials",
          requiredForBenchmark: "(required for benchmark)",
          optional: "(optional)",
          openaiBaseUrl: "OpenAI Base URL",
          openaiApiKey: "OpenAI API Key",
          attackMethods: "Attack Methods",
          selected: "selected",
          selectAll: "Select All",
          clear: "Clear",
          methodIntro: "Intro",
          methodPaper: "Paper",
          methodRepo: "Source",
          methodNoRef: "No public links",
          simpleMode: "Simple",
          managedMode: "Managed",
          advancedMode: "Advanced",
          simpleModeTitle: "One-click Full Test (Default)",
          simpleModeDesc: "Target model name and API credentials are required. The system will run attack + benchmark + evaluate automatically.",
          managedModeTitle: "Managed Model Test",
          managedModeDesc: "Select target model from managed list. No Base URL / API Key required. The platform credentials are used for the full test pipeline.",
          managedTargetModel: "Managed Target Model",
          managedSelectPlaceholder: "Select managed model",
          managedNoModels: "No managed target models available. Ask admin to configure them first.",
          managedPolicy: "Resource Policy",
          managedPolicyHint: (global: number, perIp: number, cooldown: number) =>
            `Global active limit ${global}, per-client active limit ${perIp}, client submit cooldown ${cooldown}s.`,
          managedAccessCode: "Invite Code",
          managedAccessCodeHint: "Users outside admin whitelist need an invite code.",
          errManagedModel: "Please select a managed target model.",
          simpleAutoPlanTitle: "Auto Test Plan",
          simpleAutoMode: "Run Mode",
          simpleAutoStages: "Stages",
          simpleAutoDataset: "Dataset",
          simpleAutoMethods: "Attack Methods",
          simpleAutoBenchmark: "Benchmark Config",
          simpleAutoEval: "Eval Profile",
          simpleSubmit: "Start Auto Full Test",
          errSimpleTargetModel: "Please provide target model name.",
          errSimpleCreds: "Please provide API Base URL and API Key.",
          attackConfigPath: "Attack Config Path (directory or .yaml)",
          attackConfigHelp: "Use a directory to run all yaml files, or a single yaml path to run one method.",
          benchmarkSettings: "Benchmark Settings",
          benchmarkConfigPath: "Benchmark Config Path",
          benchmarkConfigFile: "Benchmark Config File",
          selectBenchmarkConfigFile: "Select benchmark config file",
          skipBenchmarkStage: "Skip benchmark stage",
          manualBenchmarkConfigPath: "Manual benchmark config path",
          targetOpenaiBaseUrl: "Target OpenAI Base URL",
          targetOpenaiApiKey: "Target OpenAI API Key",
          benchmarkReuseHint: "Benchmark will reuse target model settings from Attack section in full pipeline mode.",
          runtimeConfigHint: "Runtime config is generated from template; top-level benchmark model is auto-bound to target model.",
          evaluateSettings: "Evaluate Settings",
          evalProfile: "Eval Profile",
          resultsRoot: "Results Root",
          useExistingRunManifest: "Use Existing Run Manifest (optional)",
          manualManifestPath: "Manual manifest path",
          resultManifestPath: "Result Manifest Path",
          resultManifestPathOptional: "Result Manifest Path (optional)",
          leaveEmptyManifest: "Leave empty to use this run's attack outputs",
          submitting: "Submitting...",
          preparing: "Preparing...",
          reset: "Reset",
          runPreview: "Run Preview",
          stages: "Stages",
          targetModel: "Target Model",
          attackMethodsCount: "Attack Methods",
          benchmarkConfig: "Benchmark Config",
          checklist: "Checklist",
          formLooksGood: "Form looks good. Ready to start.",
          isolationHint: "Artifacts and intermediate outputs are isolated by run id, avoiding cross-run pollution.",
          warnSelectMethod: "Select at least one attack method.",
          warnBenchmarkCreds: "Benchmark needs target model base_url and api_key.",
          warnEvalManifest: "Eval-only mode requires a manifest.",
          errModelNameQuick: "Model name is required in quick attack mode.",
          errDatasetQuick: "Dataset is required in quick attack mode.",
          errAttackConfig: "Attack config path is required when quick attack is disabled.",
          errBenchmarkConfig: "Benchmark config path is required in benchmark_only mode.",
          errTargetModelBenchmark: "Target model name is required when benchmark stage is enabled.",
          errTargetCredsBenchmark: "Target model base_url and api_key are required when benchmark stage is enabled.",
          errResultManifest: "Result manifest is required in eval_only mode."
        };

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
  const [benchmarkConfigOptions, setBenchmarkConfigOptions] = useState<string[]>(["benchmark/configs/run.yaml"]);
  const [benchmarkManualPathEnabled, setBenchmarkManualPathEnabled] = useState(false);
  const [simpleMode, setSimpleMode] = useState(true);
  const [managedMode, setManagedMode] = useState(false);
  const [managedTargetModels, setManagedTargetModels] = useState<ManagedTargetModel[]>([]);
  const [managedPolicy, setManagedPolicy] = useState<ManagedModePolicy | null>(null);

  useEffect(() => {
    let alive = true;
    void (async () => {
      setInitializing(true);
      const [methodsResult, datasetsResult, runsResult, attackConfigResult, benchmarkConfigResult, managedModelsResult] =
        await Promise.allSettled([
          getQuickAttackMethods(),
          getQuickAttackDatasets(),
          getRuns(),
          getAttackConfigOptions(),
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

      if (managedModelsResult.status === "fulfilled") {
        const models = (managedModelsResult.value.models || []).filter((item) => !!item.id && !!item.target_model_name);
        setManagedTargetModels(models);
        setManagedPolicy(managedModelsResult.value.policy || null);
        if (models.length > 0) {
          setPayload((prev) => ({
            ...prev,
            managed_target_model_id: prev.managed_target_model_id && models.some((item) => item.id === prev.managed_target_model_id)
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

  const isAttackMode = payload.mode === "attack_only" || payload.mode === "full_pipeline";
  const isBenchmarkMode = payload.mode === "benchmark_only" || payload.mode === "full_pipeline";
  const isEvaluateMode = payload.mode === "eval_only" || payload.mode === "full_pipeline";

  const selectedCount = useMemo(() => payload.quick_attack_methods.length, [payload.quick_attack_methods]);
  const selectedDataset = useMemo(
    () => datasetOptions.find((item) => item.key === payload.quick_dataset_key) || null,
    [datasetOptions, payload.quick_dataset_key]
  );
  const selectedManagedModel = useMemo(
    () => managedTargetModels.find((item) => item.id === payload.managed_target_model_id) || null,
    [managedTargetModels, payload.managed_target_model_id]
  );
  const managedInviteCodeRequired = !!managedPolicy?.invite_code_required;
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
      rows.push(formatStageName("attack", locale));
    }
    if (benchmarkWillRun) {
      rows.push(formatStageName("benchmark", locale));
    } else if (isBenchmarkMode) {
      rows.push(
        locale === "zh"
          ? `${formatStageName("benchmark", locale)}（跳过）`
          : `${formatStageName("benchmark", locale)} (skipped)`
      );
    }
    if (isEvaluateMode) {
      rows.push(formatStageName("evaluate", locale));
    }
    return rows;
  }, [benchmarkWillRun, isAttackMode, isBenchmarkMode, isEvaluateMode, locale]);
  const autoDatasetKey = useMemo(
    () => datasetOptions[0]?.key || payload.quick_dataset_key || "teleai_samples_500_500",
    [datasetOptions, payload.quick_dataset_key]
  );
  const autoBenchmarkConfigPath = useMemo(
    () => benchmarkConfigOptions[0] || payload.benchmark_config_path || "benchmark/configs/run.yaml",
    [benchmarkConfigOptions, payload.benchmark_config_path]
  );
  const autoMethodList = useMemo(
    () => (methodOptions.length ? methodOptions : fallbackMethodOptions),
    [methodOptions]
  );
  const autoStageSummary = useMemo(
    () => [
      formatStageName("attack", locale),
      formatStageName("benchmark", locale),
      formatStageName("evaluate", locale)
    ].join(" -> "),
    [locale]
  );
  const previewWarnings = useMemo(() => {
    const hints: string[] = [];
    if (isAttackMode && payload.quick_attack_enabled && !payload.quick_attack_methods.length) {
      hints.push(text.warnSelectMethod);
    }
    if (benchmarkWillRun && (!payload.quick_openai_base_url.trim() || !payload.quick_openai_api_key.trim())) {
      hints.push(text.warnBenchmarkCreds);
    }
    if (
      payload.mode === "eval_only" &&
      !(selectedManifestSourceRun?.result_manifest?.trim() || payload.result_manifest.trim())
    ) {
      hints.push(text.warnEvalManifest);
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
    selectedManifestSourceRun,
    text
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

    if (managedMode) {
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
        const message = err instanceof ApiError ? err.message : String(err);
        setError(message);
      } finally {
        setSubmitting(false);
      }
      return;
    }

    if (simpleMode) {
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
        const message = err instanceof ApiError ? err.message : String(err);
        setError(message);
      } finally {
        setSubmitting(false);
      }
      return;
    }

    const effectiveResultManifest =
      payload.mode === "eval_only" && selectedManifestSourceRun
        ? selectedManifestSourceRun.result_manifest
        : payload.result_manifest;

    if (isAttackMode) {
      if (payload.quick_attack_enabled) {
        if (!payload.quick_target_model_name.trim()) {
          setError(text.errModelNameQuick);
          return;
        }
        if (!payload.quick_dataset_key.trim()) {
          setError(text.errDatasetQuick);
          return;
        }
        if (!payload.quick_attack_methods.length) {
          setError(text.warnSelectMethod);
          return;
        }
      } else if (!payload.attack_config_dir.trim()) {
        setError(text.errAttackConfig);
        return;
      }
    }

    if (payload.mode === "benchmark_only" && !payload.benchmark_config_path.trim()) {
      setError(text.errBenchmarkConfig);
      return;
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
      quick_dataset_key: isAttackMode ? payload.quick_dataset_key : "teleai_samples_500_500",
      managed_target_model_id: "",
      managed_access_code: ""
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
        <p className="label">{text.runsConsole}</p>
        <h2 className="title-gradient font-headline text-2xl font-semibold">{text.newRun}</h2>
        <p className="mt-2 text-sm text-slate-600">{text.pageDesc}</p>
        <div className="hud-strip mt-2">
          <span className="hud-pill">{text.missionBuilder}</span>
          <span className="hud-pill">{text.pipelineComposer}</span>
          <span className="hud-pill hud-pill-live">
            <span className="refresh-dot" />
            {text.ready}
          </span>
        </div>
      </div>
      {initializing ? (
        <p aria-live="polite" className="notice mb-4 inline-flex items-center gap-2 text-slate-700">
          <span className="refresh-dot" />
          {text.loadingConfig}
        </p>
      ) : null}

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <button
          className={!managedMode && simpleMode ? "btn btn-primary" : "btn"}
          onClick={() => {
            setSimpleMode(true);
            setManagedMode(false);
            setPayload((prev) => ({ ...prev, managed_target_model_id: "", managed_access_code: "" }));
            setError("");
          }}
          type="button"
        >
          {text.simpleMode}
        </button>
        <button
          className={managedMode ? "btn btn-primary" : "btn"}
          onClick={() => {
            setManagedMode(true);
            setSimpleMode(false);
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
            setError("");
          }}
          type="button"
        >
          {text.managedMode}
        </button>
        <button
          className={!managedMode && !simpleMode ? "btn btn-primary" : "btn"}
          onClick={() => {
            setSimpleMode(false);
            setManagedMode(false);
            setPayload((prev) => ({ ...prev, managed_target_model_id: "", managed_access_code: "" }));
            setError("");
          }}
          type="button"
        >
          {text.advancedMode}
        </button>
      </div>

      <form aria-busy={submitting || initializing} onSubmit={onSubmit}>
        {managedMode ? (
          <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
            <div className="space-y-5 xl:col-span-8 reveal-grid">
              <article className="section-card">
                <p className="label mb-3">{text.managedModeTitle}</p>
                <p className="mb-4 text-sm text-slate-600">{text.managedModeDesc}</p>
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <label>
                    <span className="label mb-1 block">{text.runNameOptional}</span>
                    <input
                      className="input"
                      onChange={(event) => setPayload((prev) => ({ ...prev, name: event.target.value }))}
                      placeholder="e.g. managed-gpt54-nightly"
                      value={payload.name}
                    />
                  </label>
                  <label>
                    <span className="label mb-1 block">{text.managedTargetModel}</span>
                    <select
                      className="select"
                      onChange={(event) => {
                        const model = managedTargetModels.find((item) => item.id === event.target.value) || null;
                        setPayload((prev) => ({
                          ...prev,
                          managed_target_model_id: event.target.value,
                          quick_target_model_name: model?.target_model_name || prev.quick_target_model_name
                        }));
                      }}
                      value={payload.managed_target_model_id || ""}
                    >
                      <option value="">{managedTargetModels.length ? text.managedSelectPlaceholder : text.managedNoModels}</option>
                      {managedTargetModels.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.label}
                        </option>
                      ))}
                    </select>
                    {selectedManagedModel?.description ? (
                      <p className="mt-1 text-xs text-slate-600">{selectedManagedModel.description}</p>
                    ) : null}
                  </label>
                  {managedPolicy?.access_control_enabled ? (
                    <label className="md:col-span-2">
                      <span className="label mb-1 block">{text.managedAccessCode}</span>
                      <input
                        className="input mono"
                        onChange={(event) => setPayload((prev) => ({ ...prev, managed_access_code: event.target.value }))}
                        placeholder={managedInviteCodeRequired ? "required-invite-code" : "optional-invite-code"}
                        value={payload.managed_access_code || ""}
                      />
                      <p className="mt-1 text-xs text-slate-600">{text.managedAccessCodeHint}</p>
                    </label>
                  ) : null}
                </div>
                {managedPolicy ? (
                  <p className="tech-subpanel mt-4 p-3 text-sm text-slate-700">
                    {text.managedPolicyHint(
                      managedPolicy.max_active_runs_global,
                      managedPolicy.max_active_runs_per_ip,
                      managedPolicy.min_interval_seconds
                    )}
                  </p>
                ) : null}
              </article>

              {error ? (
                <p aria-live="assertive" className="notice notice-error" role="alert">
                  {error}
                </p>
              ) : null}

              <div className="flex flex-wrap items-center gap-2">
                <button
                  className={submitting ? "btn btn-primary btn-busy" : "btn btn-primary"}
                  disabled={
                    submitting ||
                    initializing ||
                    !managedTargetModels.length ||
                    (managedInviteCodeRequired && !(payload.managed_access_code || "").trim())
                  }
                  type="submit"
                >
                  {submitting ? text.submitting : initializing ? text.preparing : text.simpleSubmit}
                </button>
                <button
                  className="btn"
                  onClick={() => {
                    const first = managedTargetModels[0] || null;
                    setPayload({
                      ...defaultPayload,
                      managed_target_model_id: first?.id || "",
                      quick_target_model_name: first?.target_model_name || ""
                    });
                    setManifestSourceRunId("");
                    setBenchmarkManualPathEnabled(false);
                    setManagedMode(true);
                    setSimpleMode(false);
                    setError("");
                  }}
                  type="button"
                >
                  {text.reset}
                </button>
              </div>
            </div>

            <aside className="space-y-4 xl:col-span-4 xl:sticky xl:top-6 xl:self-start reveal-grid">
              <article className="stat-card">
                <p className="label mb-2">{text.simpleAutoPlanTitle}</p>
                <dl className="space-y-2 text-sm text-slate-700">
                  <div>
                    <dt className="label">{text.simpleAutoMode}</dt>
                    <dd>{formatRunMode("full_pipeline", locale)}</dd>
                  </div>
                  <div>
                    <dt className="label">{text.simpleAutoStages}</dt>
                    <dd className="mono text-xs">{autoStageSummary}</dd>
                  </div>
                  <div>
                    <dt className="label">{text.targetModel}</dt>
                    <dd>{selectedManagedModel?.target_model_name || "-"}</dd>
                  </div>
                  <div>
                    <dt className="label">{text.simpleAutoDataset}</dt>
                    <dd className="mono text-xs">{autoDatasetKey}</dd>
                  </div>
                  <div>
                    <dt className="label">{text.simpleAutoMethods}</dt>
                    <dd>{autoMethodList.length}</dd>
                  </div>
                  <div>
                    <dt className="label">{text.simpleAutoBenchmark}</dt>
                    <dd className="mono text-xs">{autoBenchmarkConfigPath}</dd>
                  </div>
                  <div>
                    <dt className="label">{text.simpleAutoEval}</dt>
                    <dd>full</dd>
                  </div>
                </dl>
              </article>

              <article className="stat-card">
                <p className="label mb-2">{text.managedPolicy}</p>
                <p className="text-xs text-slate-600">
                  {managedPolicy
                    ? text.managedPolicyHint(
                        managedPolicy.max_active_runs_global,
                        managedPolicy.max_active_runs_per_ip,
                        managedPolicy.min_interval_seconds
                      )
                    : "-"}
                </p>
              </article>
            </aside>
          </div>
        ) : simpleMode ? (
          <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
            <div className="space-y-5 xl:col-span-8 reveal-grid">
              <article className="section-card">
                <p className="label mb-3">{text.simpleModeTitle}</p>
                <p className="mb-4 text-sm text-slate-600">{text.simpleModeDesc}</p>
                <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                  <label>
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
              </article>

              {error ? (
                <p aria-live="assertive" className="notice notice-error" role="alert">
                  {error}
                </p>
              ) : null}

              <div className="flex flex-wrap items-center gap-2">
                <button className={submitting ? "btn btn-primary btn-busy" : "btn btn-primary"} disabled={submitting || initializing} type="submit">
                  {submitting ? text.submitting : initializing ? text.preparing : text.simpleSubmit}
                </button>
                <button
                  className="btn"
                  onClick={() => {
                    setPayload(defaultPayload);
                    setManifestSourceRunId("");
                    setBenchmarkManualPathEnabled(false);
                    setSimpleMode(true);
                    setManagedMode(false);
                    setError("");
                  }}
                  type="button"
                >
                  {text.reset}
                </button>
              </div>
            </div>

            <aside className="space-y-4 xl:col-span-4 xl:sticky xl:top-6 xl:self-start reveal-grid">
              <article className="stat-card">
                <p className="label mb-2">{text.simpleAutoPlanTitle}</p>
                <dl className="space-y-2 text-sm text-slate-700">
                  <div>
                    <dt className="label">{text.simpleAutoMode}</dt>
                    <dd>{formatRunMode("full_pipeline", locale)}</dd>
                  </div>
                  <div>
                    <dt className="label">{text.simpleAutoStages}</dt>
                    <dd className="mono text-xs">{autoStageSummary}</dd>
                  </div>
                  <div>
                    <dt className="label">{text.targetModel}</dt>
                    <dd>{payload.quick_target_model_name || "-"}</dd>
                  </div>
                  <div>
                    <dt className="label">{text.simpleAutoDataset}</dt>
                    <dd className="mono text-xs">{autoDatasetKey}</dd>
                  </div>
                  <div>
                    <dt className="label">{text.simpleAutoMethods}</dt>
                    <dd>{autoMethodList.length}</dd>
                  </div>
                  <div>
                    <dt className="label">{text.simpleAutoBenchmark}</dt>
                    <dd className="mono text-xs">{autoBenchmarkConfigPath}</dd>
                  </div>
                  <div>
                    <dt className="label">{text.simpleAutoEval}</dt>
                    <dd>full</dd>
                  </div>
                </dl>
              </article>
            </aside>
          </div>
        ) : (
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
                <label>
                  <span className="label mb-1 block">{text.mode}</span>
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
                    {text.quickAttack}
                  </label>
                </div>

                {payload.quick_attack_enabled ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                      <label>
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
                      <label>
                        <span className="label mb-1 block">{text.dataset}</span>
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
                              {item.exists ? item.name : `${item.name} (${text.unavailable})`}
                            </option>
                          ))}
                        </select>
                        {selectedDataset ? <p className="mt-1 text-xs text-slate-600">{selectedDataset.description}</p> : null}
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

                    <details className="tech-subpanel p-3" open={selectedCount === 0}>
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
                          <button
                            className="btn"
                            onClick={() => setPayload((prev) => ({ ...prev, quick_attack_methods: [] }))}
                            type="button"
                          >
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
                                  <input
                                    checked={selected}
                                    className="sr-only"
                                    onChange={() => toggleMethod(method)}
                                    type="checkbox"
                                  />
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
                ) : (
                  <label>
                    <span className="label mb-1 block">{text.attackConfigPath}</span>
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
                    <p className="mt-1 text-xs text-slate-600">{text.attackConfigHelp}</p>
                  </label>
                )}
              </article>
            ) : null}

            {isBenchmarkMode ? (
              <article className="section-card">
                <p className="label mb-3">{text.benchmarkSettings}</p>
                <div className="space-y-3">
                  {showBenchmarkManualPath ? (
                    <label>
                      <span className="label mb-1 block">{text.benchmarkConfigPath}</span>
                      <input
                        className="input mono"
                        onChange={(event) => setPayload((prev) => ({ ...prev, benchmark_config_path: event.target.value }))}
                        placeholder="benchmark/configs/run/code/run_code_merged_model_only.yaml"
                        value={payload.benchmark_config_path}
                      />
                    </label>
                  ) : (
                    <label>
                      <span className="label mb-1 block">{text.benchmarkConfigFile}</span>
                      <select
                        className="select mono"
                        onChange={(event) => setPayload((prev) => ({ ...prev, benchmark_config_path: event.target.value }))}
                        value={payload.benchmark_config_path}
                      >
                        <option value="">
                          {payload.mode === "benchmark_only" ? text.selectBenchmarkConfigFile : text.skipBenchmarkStage}
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
                    {text.manualBenchmarkConfigPath}
                  </label>
                </div>

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
                <p className="mt-2 text-xs text-slate-600">{text.runtimeConfigHint}</p>
              </article>
            ) : null}

            {isEvaluateMode ? (
              <article className="section-card">
                <p className="label mb-3">{text.evaluateSettings}</p>
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
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
                  <label>
                    <span className="label mb-1 block">{text.resultsRoot}</span>
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
                      <span className="label mb-1 block">{text.useExistingRunManifest}</span>
                      <select
                        className="select"
                        onChange={(event) => setManifestSourceRunId(event.target.value)}
                        value={manifestSourceRunId}
                      >
                        <option value="">{text.manualManifestPath}</option>
                        {manifestSourceRuns.map((item) => (
                          <option key={item.run_id} value={item.run_id}>
                            {item.name} ({item.run_id.slice(0, 8)})
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      <span className="label mb-1 block">{text.resultManifestPath}</span>
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
                    <span className="label mb-1 block">{text.resultManifestPathOptional}</span>
                    <input
                      className="input mono"
                      onChange={(event) => setPayload((prev) => ({ ...prev, result_manifest: event.target.value }))}
                      placeholder={text.leaveEmptyManifest}
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
                {submitting ? text.submitting : initializing ? text.preparing : modeSubmitLabel(payload.mode, locale)}
              </button>
              <button
                className="btn"
                onClick={() => {
                  setPayload(defaultPayload);
                  setManifestSourceRunId("");
                  setBenchmarkManualPathEnabled(false);
                  setSimpleMode(true);
                  setManagedMode(false);
                  setError("");
                }}
                type="button"
              >
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
                  <dd>{isAttackMode && payload.quick_attack_enabled ? selectedCount : 0}</dd>
                </div>
                <div>
                  <dt className="label">{text.benchmarkConfig}</dt>
                  <dd className="mono text-xs">{payload.benchmark_config_path || "-"}</dd>
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
              <p className="mt-3 text-xs text-slate-600">{text.isolationHint}</p>
            </article>
          </aside>
        </div>
        )}
      </form>
    </section>
  );
}
