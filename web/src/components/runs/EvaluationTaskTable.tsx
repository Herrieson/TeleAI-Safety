"use client";

import { useI18n } from "@/components/common/LocaleProvider";
import type { RunMetricTask } from "@/lib/types";

type EvaluationTaskTableProps = {
  tasks: RunMetricTask[];
  loading: boolean;
  exportingTaskId: string | null;
  onExport: (taskId: string) => void;
  frrUnavailable?: boolean;
};

function formatRatio(value: number | null, locale: "zh" | "en"): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "-";
  }
  const localeTag = locale === "zh" ? "zh-CN" : "en-US";
  if (value >= 0 && value <= 1) {
    return `${(value * 100).toLocaleString(localeTag, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    })}%`;
  }
  return value.toLocaleString(localeTag, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 6
  });
}

function formatCount(value: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "-";
  }
  return String(value);
}

export function EvaluationTaskTable({ tasks, loading, exportingTaskId, onExport, frrUnavailable = false }: EvaluationTaskTableProps) {
  const { locale } = useI18n();
  const text =
    locale === "zh"
      ? {
          title: "评估任务",
          loading: "正在加载评估任务...",
          empty: "暂无评估任务明细。",
          task: "任务",
          scorer: "评分器",
          samples: "样本",
          skipped: "跳过",
          asr: "ASR",
          asrStrict: "ASR 严格",
          asrEffective: "ASR 有效",
          frr: "FRR",
          frrInvalidRate: "FRR 无效率",
          reportPath: "报告路径",
          inputFile: "输入文件",
          action: "操作",
          exportReport: "导出评估报告",
          exporting: "导出中..."
        }
      : {
          title: "Evaluation Tasks",
          loading: "Loading evaluation tasks...",
          empty: "No evaluation task details yet.",
          task: "Task",
          scorer: "Scorer",
          samples: "Samples",
          skipped: "Skipped",
          asr: "ASR",
          asrStrict: "ASR Strict",
          asrEffective: "ASR Effective",
          frr: "FRR",
          frrInvalidRate: "FRR Invalid",
          reportPath: "Report Path",
          inputFile: "Input File",
          action: "Action",
          exportReport: "Export Report",
          exporting: "Exporting..."
        };

  return (
    <div className="mt-5">
      <p className="label mb-3">{text.title}</p>
      {loading ? <p className="notice text-slate-600">{text.loading}</p> : null}
      {!loading && tasks.length === 0 ? <p className="notice text-slate-600">{text.empty}</p> : null}
      {!loading && tasks.length > 0 ? (
        <div className="data-table-wrap">
          <table className="data-table min-w-[1400px]">
            <thead>
              <tr>
                <th className="font-semibold">{text.task}</th>
                <th className="font-semibold">{text.scorer}</th>
                <th className="font-semibold">{text.samples}</th>
                <th className="font-semibold">{text.skipped}</th>
                <th className="font-semibold">{text.asr}</th>
                <th className="font-semibold">{text.asrStrict}</th>
                <th className="font-semibold">{text.asrEffective}</th>
                <th className="font-semibold">{text.frr}</th>
                <th className="font-semibold">{text.frrInvalidRate}</th>
                <th className="font-semibold">{text.reportPath}</th>
                <th className="font-semibold">{text.inputFile}</th>
                <th className="font-semibold">{text.action}</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((task) => (
                <tr className="text-sm transition-colors" key={task.task_id}>
                  <td className="text-slate-700">{task.attack_group || task.attack_run || "-"}</td>
                  <td className="text-slate-700">{task.scorer || "-"}</td>
                  <td className="text-slate-700">
                    {formatCount(task.total_samples)} / {formatCount(task.attack_success_samples)}
                  </td>
                  <td className="text-slate-700">{formatCount(task.skipped_samples)}</td>
                  <td className="text-slate-700">{formatRatio(task.asr, locale)}</td>
                  <td className="text-slate-700">{formatRatio(task.asr_strict, locale)}</td>
                  <td className="text-slate-700">{formatRatio(task.asr_effective, locale)}</td>
                  <td className="text-slate-700">{frrUnavailable ? "N/A" : formatRatio(task.frr, locale)}</td>
                  <td className="text-slate-700">{frrUnavailable ? "N/A" : formatRatio(task.frr_invalid_rate, locale)}</td>
                  <td>
                    <span className="mono text-xs text-slate-700">{task.report_path || "-"}</span>
                  </td>
                  <td>
                    <span className="mono text-xs text-slate-700">{task.input_file || "-"}</span>
                  </td>
                  <td>
                    <button
                      className={exportingTaskId === task.task_id ? "btn btn-busy" : "btn"}
                      disabled={exportingTaskId === task.task_id}
                      onClick={() => onExport(task.task_id)}
                      type="button"
                    >
                      {exportingTaskId === task.task_id ? text.exporting : text.exportReport}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
