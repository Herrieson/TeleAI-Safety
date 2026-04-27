import type { RunCreatePayload, RunMode } from "@/lib/types";

export type NewRunViewMode = "simple" | "managed" | "advanced";

export const fallbackMethodOptions = [
  "artprompt",
  "cipher",
  "deep_inception",
  "dra",
  "jailbroken",
  "morpheus_gapfill",
  "pair",
  "rene"
];

export const DEFAULT_QUICK_DATASET_KEY = "teleai_samples_500_500";

export const defaultRunPayload: RunCreatePayload = {
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
  quick_dataset_key: DEFAULT_QUICK_DATASET_KEY,
  managed_target_model_id: "",
  managed_access_code: ""
};

export const runModeOptions: RunMode[] = ["attack_only", "full_pipeline", "benchmark_only"];
