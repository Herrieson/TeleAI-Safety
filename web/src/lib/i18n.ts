import type { RunMode, RunStatus, StageName } from "@/lib/types";

export type Locale = "zh" | "en";

export const DEFAULT_LOCALE: Locale = "zh";
export const LOCALE_STORAGE_KEY = "teleai_web_locale";

const localeTagMap: Record<Locale, string> = {
  zh: "zh-CN",
  en: "en-US"
};

const htmlLangMap: Record<Locale, string> = {
  zh: "zh-CN",
  en: "en"
};

const statusLabels: Record<Locale, Record<RunStatus, string>> = {
  zh: {
    pending: "等待中",
    running: "运行中",
    succeeded: "成功",
    failed: "失败",
    canceled: "已取消"
  },
  en: {
    pending: "Pending",
    running: "Running",
    succeeded: "Succeeded",
    failed: "Failed",
    canceled: "Canceled"
  }
};

const modeLabels: Record<Locale, Record<RunMode, string>> = {
  zh: {
    attack_only: "仅攻击",
    benchmark_only: "仅基准测试",
    eval_only: "仅评估",
    full_pipeline: "完整流水线"
  },
  en: {
    attack_only: "Attack Only",
    benchmark_only: "Benchmark Only",
    eval_only: "Eval Only",
    full_pipeline: "Full Pipeline"
  }
};

const stageLabels: Record<Locale, Record<StageName, string>> = {
  zh: {
    attack: "攻击",
    benchmark: "基准测试",
    evaluate: "评估"
  },
  en: {
    attack: "Attack",
    benchmark: "Benchmark",
    evaluate: "Evaluate"
  }
};

export function isLocale(value: string | null | undefined): value is Locale {
  return value === "zh" || value === "en";
}

export function toLocaleTag(locale: Locale): string {
  return localeTagMap[locale];
}

export function toHtmlLang(locale: Locale): string {
  return htmlLangMap[locale];
}

export function formatRunStatus(status: RunStatus, locale: Locale): string {
  return statusLabels[locale][status];
}

export function formatRunMode(mode: RunMode, locale: Locale): string {
  return modeLabels[locale][mode];
}

export function formatStageName(stage: string, locale: Locale): string {
  const labels = stageLabels[locale] as Record<string, string>;
  return labels[stage] || stage;
}

export function formatDateTime(value: string | number | Date, locale: Locale): string {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return date.toLocaleString(toLocaleTag(locale));
}
