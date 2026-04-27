export type RunMode = "attack_only" | "benchmark_only" | "eval_only" | "full_pipeline";
export type RunStatus = "pending" | "running" | "succeeded" | "failed" | "canceled";
export type StageName = "attack" | "benchmark" | "evaluate";
export type StageStatus = "pending" | "running" | "succeeded" | "failed" | "canceled";
export type AuthRole = "admin" | "user";

export type AuthUser = {
  username: string;
  role: AuthRole;
};

export type RunStage = {
  stage: StageName;
  status: StageStatus;
  command: string;
  log_path: string;
  started_at: string | null;
  updated_at: string;
  ended_at: string | null;
  exit_code: number | null;
  error: string;
};

export type Artifact = {
  artifact_id: string;
  stage: StageName;
  type: string;
  path: string;
  size_bytes: number;
  created_at: string;
};

export type Run = {
  run_id: string;
  name: string;
  mode: RunMode;
  status: RunStatus;
  attack_config_dir: string;
  benchmark_config_path: string;
  eval_profile: string;
  results_root: string;
  result_manifest: string;
  quick_attack_enabled: boolean;
  quick_target_model_name: string;
  quick_openai_base_url: string;
  quick_attack_methods: string[];
  quick_dataset_key: string;
  managed_target_model_id: string;
  owner_username: string;
  requester_ip: string;
  created_at: string;
  updated_at: string;
  ended_at: string | null;
  error: string;
  stages: RunStage[];
  artifacts: Artifact[];
  metric_summary: Record<string, unknown>;
};

export type RunCreatePayload = {
  name: string;
  mode: RunMode;
  attack_config_dir: string;
  benchmark_config_path: string;
  eval_profile: string;
  results_root: string;
  result_manifest: string;
  quick_attack_enabled: boolean;
  quick_target_model_name: string;
  quick_openai_base_url: string;
  quick_openai_api_key: string;
  quick_attack_methods: string[];
  quick_dataset_key: string;
  managed_target_model_id?: string;
  managed_access_code?: string;
  requester_ip?: string;
};

export type LoginPayload = {
  username: string;
  password: string;
};

export type LoginResponse = {
  user: AuthUser;
};

export type RunLogsResponse = {
  run_id: string;
  stage: string;
  log_path: string;
  content: string;
};

export type RunArtifactsResponse = {
  run_id: string;
  count: number;
  artifacts: Artifact[];
};

export type RunMetricsSummaryResponse = {
  run_id: string;
  metric_summary: Record<string, unknown>;
};

export type RunMetricTask = {
  task_id: string;
  attack_run: string;
  attack_group: string;
  scorer: string;
  total_samples: number | null;
  skipped_samples: number | null;
  attack_success_samples: number | null;
  asr: number | null;
  asr_strict: number | null;
  asr_effective: number | null;
  frr: number | null;
  frr_invalid_rate: number | null;
  report_path: string;
  input_file: string;
};

export type RunMetricTasksResponse = {
  run_id: string;
  count: number;
  tasks: RunMetricTask[];
};

export type RunMetricTaskReportResponse = {
  run_id: string;
  task_id: string;
  filename: string;
  content: string;
};

export type QuickAttackMethodsResponse = {
  count: number;
  methods: string[];
};

export type QuickAttackDataset = {
  key: string;
  name: string;
  path: string;
  description: string;
  exists: boolean;
};

export type QuickAttackDatasetsResponse = {
  count: number;
  datasets: QuickAttackDataset[];
};

export type ManagedTargetModel = {
  id: string;
  label: string;
  target_model_name: string;
  description: string;
};

export type ManagedModePolicy = {
  max_active_runs_global: number;
  max_active_runs_per_ip: number;
  min_interval_seconds: number;
  access_control_enabled?: boolean;
  ip_whitelisted?: boolean;
  invite_code_required?: boolean;
};

export type ManagedTargetModelsResponse = {
  enabled: boolean;
  count: number;
  models: ManagedTargetModel[];
  policy?: ManagedModePolicy;
};

export type AttackConfigOptionsResponse = {
  directory_count: number;
  yaml_file_count: number;
  directories: string[];
  yaml_files: string[];
};

export type BenchmarkConfigOptionsResponse = {
  yaml_file_count: number;
  yaml_files: string[];
};

export type LeaderboardMetricBetter = "higher" | "lower" | "absolute_zero";
export type LeaderboardMetricFormat = "number" | "percent";

export type LeaderboardMetric = {
  key: string;
  label: string;
  better: LeaderboardMetricBetter;
  format: LeaderboardMetricFormat;
  precision: number;
};

export type LeaderboardRow = {
  model: string;
  metrics: Record<string, number | null>;
};

export type LeaderboardResponse = {
  generated_at: string;
  source_csv: string;
  source_updated_at: string;
  model_count: number;
  metric_count: number;
  metrics: LeaderboardMetric[];
  rows: LeaderboardRow[];
};

export type MechanismMetricSnapshot = {
  metric: string;
  direction: "higher_better" | "lower_better";
  best_model: string | null;
  best_value: number | null;
  worst_model: string | null;
  worst_value: number | null;
  average_value: number | null;
};

export type MechanismOverviewItem = {
  mechanism_id: string;
  mechanism_name: string;
  module: string;
  output_file: string;
  metric_count: number;
  model_count: number;
  top_model: string | null;
  top_score: number | null;
  metrics: MechanismMetricSnapshot[];
};

export type MechanismOverviewResponse = {
  available: boolean;
  output_root: string;
  dashboard_available: boolean;
  dashboard_path: string;
  generated_at: number | null;
  mechanism_count: number;
  model_count: number;
  mechanisms: MechanismOverviewItem[];
};

export type MechanismLeaderboardMechanism = {
  mechanism_id: string;
  mechanism_name: string;
};

export type MechanismLeaderboardRank = {
  rank: number | null;
  score: number | null;
};

export type MechanismLeaderboardRow = {
  model_id: string;
  covered: number;
  avg_rank: number | null;
  mechanism_ranks: Record<string, MechanismLeaderboardRank>;
};

export type MechanismLeaderboardResponse = {
  available: boolean;
  generated_at: number | null;
  mechanism_count: number;
  model_count: number;
  mechanisms: MechanismLeaderboardMechanism[];
  rows: MechanismLeaderboardRow[];
};
