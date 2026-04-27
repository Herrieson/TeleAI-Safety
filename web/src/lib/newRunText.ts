import type { Locale } from "@/lib/i18n";

export type NewRunText = {
  runsConsole: string;
  newRun: string;
  openGuide: string;
  pageDesc: string;
  mobileTitle: string;
  mobileDesc: string;
  mobileOpenRuns: string;
  missionBuilder: string;
  pipelineComposer: string;
  ready: string;
  loadingConfig: string;
  startTour: string;
  restartTour: string;
  tourTitle: string;
  tourStep: string;
  tourPrevious: string;
  tourNext: string;
  tourFinish: string;
  tourSkip: string;
  tourStepViewModeTitle: string;
  tourStepViewModeDesc: string;
  tourStepSimpleTitle: string;
  tourStepSimpleDesc: string;
  tourStepManagedTitle: string;
  tourStepManagedDesc: string;
  tourStepAdvancedTitle: string;
  tourStepAdvancedDesc: string;
  tourStepMethodsTitle: string;
  tourStepMethodsDesc: string;
  tourStepSubmitTitle: string;
  tourStepSubmitDesc: string;
  basicSetup: string;
  runNameOptional: string;
  mode: string;
  attackSettings: string;
  quickAttack: string;
  targetModelName: string;
  targetApiCreds: string;
  requiredForBenchmark: string;
  optional: string;
  openaiBaseUrl: string;
  openaiApiKey: string;
  attackMethods: string;
  selected: string;
  selectAll: string;
  clear: string;
  methodIntro: string;
  methodPaper: string;
  methodRepo: string;
  methodNoRef: string;
  simpleMode: string;
  managedMode: string;
  advancedMode: string;
  simpleModeTitle: string;
  simpleModeDesc: string;
  managedModeTitle: string;
  managedModeDesc: string;
  managedTargetModel: string;
  managedSelectPlaceholder: string;
  managedNoModels: string;
  managedPolicy: string;
  managedPolicyHint: (global: number, perIp: number, cooldown: number) => string;
  managedAccessCode: string;
  managedAccessCodeHint: string;
  errManagedModel: string;
  autoRunSummaryTitle: string;
  autoRunSummaryDesc: string;
  autoRunSummaryManagedDesc: string;
  autoRunSummaryStages: string;
  autoRunSummaryTarget: string;
  autoRunSummaryMonitor: string;
  managedSummaryTitle: string;
  managedSummaryDesc: string;
  simpleSubmit: string;
  errSimpleTargetModel: string;
  errSimpleCreds: string;
  attackConfigPath: string;
  attackConfigHelp: string;
  benchmarkSettings: string;
  benchmarkConfigPath: string;
  benchmarkConfigFile: string;
  selectBenchmarkConfigFile: string;
  skipBenchmarkStage: string;
  manualBenchmarkConfigPath: string;
  targetOpenaiBaseUrl: string;
  targetOpenaiApiKey: string;
  benchmarkReuseHint: string;
  runtimeConfigHint: string;
  pipelineAutoFollowup: string;
  evaluateSettings: string;
  evalProfile: string;
  resultsRoot: string;
  useExistingRunManifest: string;
  manualManifestPath: string;
  resultManifestPath: string;
  resultManifestPathOptional: string;
  leaveEmptyManifest: string;
  submitting: string;
  preparing: string;
  reset: string;
  runPreview: string;
  stages: string;
  targetModel: string;
  attackMethodsCount: string;
  benchmarkConfig: string;
  checklist: string;
  formLooksGood: string;
  warnSelectMethod: string;
  warnBenchmarkCreds: string;
  warnEvalManifest: string;
  errModelNameQuick: string;
  errAttackConfig: string;
  errBenchmarkConfig: string;
  errTargetModelBenchmark: string;
  errTargetCredsBenchmark: string;
  errResultManifest: string;
};

export function getNewRunText(locale: Locale): NewRunText {
  if (locale === "zh") {
    return {
      runsConsole: "运行控制台",
      newRun: "新建任务",
      openGuide: "查看使用引导",
      pageDesc: "",
      mobileTitle: "移动端已降级为查看模式",
      mobileDesc: "手机端主要用于查看任务状态、日志与结果。新建任务和复杂配置仍建议使用电脑访问。",
      mobileOpenRuns: "查看任务列表",
      missionBuilder: "任务编排",
      pipelineComposer: "流水线编辑器",
      ready: "就绪",
      loadingConfig: "正在加载最新配置选项...",
      startTour: "开始引导",
      restartTour: "重新查看引导",
      tourTitle: "新建任务引导",
      tourStep: "步骤",
      tourPrevious: "上一步",
      tourNext: "下一步",
      tourFinish: "完成",
      tourSkip: "跳过",
      tourStepViewModeTitle: "先选任务创建方式",
      tourStepViewModeDesc: "这里可以在简洁模式、平台托管模式和高级模式之间切换。一般用户优先使用前两种，只有需要细粒度控制时再进入高级模式。",
      tourStepSimpleTitle: "简洁模式适合直接开始",
      tourStepSimpleDesc: "只需要填写目标模型、Base URL 和 API Key，系统就会自动完成攻击、基准测试和评估，适合大多数常规使用场景。",
      tourStepManagedTitle: "平台托管模式更省事",
      tourStepManagedDesc: "如果目标模型已经由平台托管，你只需要选择模型即可，无需自己填写接口地址和密钥，最适合面向普通用户开放。",
      tourStepAdvancedTitle: "高级模式用于精细控制",
      tourStepAdvancedDesc: "只有当你需要单独跑攻击、切换完整流水线，或者手动控制执行方式时，再使用高级模式。日常使用不必先从这里开始。",
      tourStepMethodsTitle: "攻击方法在这里选择",
      tourStepMethodsDesc: "进入高级模式后，可以在这里勾选要执行的攻击方法。需要更广覆盖时可以多选，只想做定向测试时也可以只保留少数几种。",
      tourStepSubmitTitle: "最后从这里启动任务",
      tourStepSubmitDesc: "确认信息后，从这里启动任务即可。创建完成后，可以到运行列表查看执行进度和最终结果。",
      basicSetup: "基础设置",
      runNameOptional: "任务名称（可选）",
      mode: "模式",
      attackSettings: "攻击设置",
      quickAttack: "快速攻击",
      targetModelName: "目标模型名称",
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
      autoRunSummaryTitle: "系统将自动完成",
      autoRunSummaryDesc: "填写目标模型和接口信息后，系统会自动串行完成攻击、基准测试和评估，你只需要关注任务进度和结果。",
      autoRunSummaryManagedDesc: "选择托管模型后，平台会自动使用已配置资源完成攻击、基准测试和评估，无需额外填写接口细节。",
      autoRunSummaryStages: "自动执行阶段",
      autoRunSummaryTarget: "当前目标模型",
      autoRunSummaryMonitor: "任务创建后，可在运行列表中查看进度、日志和结果。",
      managedSummaryTitle: "平台托管说明",
      managedSummaryDesc: "平台托管模式更适合普通用户。只要目标模型已接入平台，就不需要再理解接口地址、密钥或测试配置。",
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
      pipelineAutoFollowup: "完整流水线会在攻击完成后自动继续执行基准测试和评估，无需额外设置。",
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
      warnSelectMethod: "请至少选择一个攻击方法。",
      warnBenchmarkCreds: "执行基准测试需要目标模型 base_url 和 api_key。",
      warnEvalManifest: "仅评估模式需要提供清单。",
      errModelNameQuick: "快速攻击模式下必须填写模型名称。",
      errAttackConfig: "关闭快速攻击时必须填写攻击配置路径。",
      errBenchmarkConfig: "benchmark_only 模式必须填写基准测试配置路径。",
      errTargetModelBenchmark: "启用 benchmark 阶段时必须填写目标模型名称。",
      errTargetCredsBenchmark: "启用 benchmark 阶段时必须填写目标模型 base_url 和 api_key。",
      errResultManifest: "eval_only 模式必须填写结果清单。"
    };
  }

  return {
    runsConsole: "Runs Console",
    newRun: "New Run",
    openGuide: "Open Guide",
    pageDesc: "",
    mobileTitle: "Mobile view is limited",
    mobileDesc: "Use phones mainly for monitoring runs, logs, and results. Full run creation stays desktop-first.",
    mobileOpenRuns: "Open Runs",
    missionBuilder: "Mission Builder",
    pipelineComposer: "Pipeline Composer",
    ready: "Ready",
    loadingConfig: "loading latest config options...",
    startTour: "Start Tour",
    restartTour: "Replay Tour",
    tourTitle: "New Run Tour",
    tourStep: "Step",
    tourPrevious: "Previous",
    tourNext: "Next",
    tourFinish: "Finish",
    tourSkip: "Skip",
    tourStepViewModeTitle: "Choose how to create a run",
    tourStepViewModeDesc: "Switch between simple, managed, and advanced modes here. Most users should start with the first two, and only use advanced mode when they need finer control.",
    tourStepSimpleTitle: "Simple mode is the fastest path",
    tourStepSimpleDesc: "Enter the target model, Base URL, and API Key here. The platform then runs attack, benchmark, and evaluation automatically for the most common workflow.",
    tourStepManagedTitle: "Managed mode is even easier",
    tourStepManagedDesc: "If the target model is already hosted by the platform, you only need to pick it from the list. No manual endpoint or key entry is required.",
    tourStepAdvancedTitle: "Advanced mode is for finer control",
    tourStepAdvancedDesc: "Use advanced mode when you need to run only attacks, choose a different execution path, or adjust the flow more explicitly. It is not the default path for most users.",
    tourStepMethodsTitle: "Pick attack methods here",
    tourStepMethodsDesc: "Inside advanced mode, select the attack methods you want to run here. Keep a few for targeted testing, or choose more for wider coverage.",
    tourStepSubmitTitle: "Start the run from here",
    tourStepSubmitDesc: "Once the inputs are ready, start the run here. After creation, you can monitor progress and results from the runs list.",
    basicSetup: "Basic Setup",
    runNameOptional: "Run Name (optional)",
    mode: "Mode",
    attackSettings: "Attack Settings",
    quickAttack: "Quick Attack",
    targetModelName: "Target Model Name",
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
    autoRunSummaryTitle: "The platform will handle",
    autoRunSummaryDesc: "After you provide the target model and API details, the system will automatically run attack, benchmark, and evaluation in sequence. You only need to watch the run and results.",
    autoRunSummaryManagedDesc: "After you choose a managed model, the platform uses its configured resources to run attack, benchmark, and evaluation automatically. No extra endpoint details are needed.",
    autoRunSummaryStages: "Automatic stages",
    autoRunSummaryTarget: "Current target model",
    autoRunSummaryMonitor: "After the run is created, you can monitor progress, logs, and results from the runs list.",
    managedSummaryTitle: "Managed mode",
    managedSummaryDesc: "Managed mode fits regular users best. If the target model is already connected to the platform, there is no need to deal with endpoints, keys, or test config details.",
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
    pipelineAutoFollowup: "Full pipeline will continue with benchmark and evaluation automatically after the attack stage.",
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
    warnSelectMethod: "Select at least one attack method.",
    warnBenchmarkCreds: "Benchmark needs target model base_url and api_key.",
    warnEvalManifest: "Eval-only mode requires a manifest.",
    errModelNameQuick: "Model name is required in quick attack mode.",
    errAttackConfig: "Attack config path is required when quick attack is disabled.",
    errBenchmarkConfig: "Benchmark config path is required in benchmark_only mode.",
    errTargetModelBenchmark: "Target model name is required when benchmark stage is enabled.",
    errTargetCredsBenchmark: "Target model base_url and api_key are required when benchmark stage is enabled.",
    errResultManifest: "Result manifest is required in eval_only mode."
  };
}
