"use client";

import { useI18n } from "@/components/common/LocaleProvider";
import type { RunMetricTask } from "@/lib/types";

type EvaluationTaskTableProps = {
  tasks: RunMetricTask[];
  loading: boolean;
  exportingTaskId: string | null;
  onExport: (taskId: string) => void;
};

function formatRatio(value: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "-";
  }
  if (value >= 0 && value <= 1) {
    return `${(value * 100).toFixed(2)}%`;
  }
  return value.toFixed(6);
}

function formatCount(value: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "-";
  }
  return String(value);
}

export function EvaluationTaskTable({ tasks, loading, exportingTaskId, onExport }: EvaluationTaskTableProps) {
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
          asr: "ASR",
          asrEffective: "ASR 有效",
          frr: "FRR",
          reportPath: "报告路径",
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
          asr: "ASR",
          asrEffective: "ASR Effective",
          frr: "FRR",
          reportPath: "Report Path",
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
          <table className="data-table min-w-[1100px]">
            <thead>
              <tr>
                <th className="font-semibold">{text.task}</th>
                <th className="font-semibold">{text.scorer}</th>
                <th className="font-semibold">{text.samples}</th>
                <th className="font-semibold">{text.asr}</th>
                <th className="font-semibold">{text.asrEffective}</th>
                <th className="font-semibold">{text.frr}</th>
                <th className="font-semibold">{text.reportPath}</th>
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
                  <td className="text-slate-700">{formatRatio(task.asr)}</td>
                  <td className="text-slate-700">{formatRatio(task.asr_effective)}</td>
                  <td className="text-slate-700">{formatRatio(task.frr)}</td>
                  <td>
                    <span className="mono text-xs text-slate-700">{task.report_path || "-"}</span>
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
