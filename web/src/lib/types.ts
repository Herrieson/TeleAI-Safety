export type RunMode = "attack_only" | "benchmark_only" | "eval_only" | "full_pipeline";
export type RunStatus = "pending" | "running" | "succeeded" | "failed" | "canceled";
export type StageName = "attack" | "benchmark" | "evaluate";
export type StageStatus = "pending" | "running" | "succeeded" | "failed" | "canceled";

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
