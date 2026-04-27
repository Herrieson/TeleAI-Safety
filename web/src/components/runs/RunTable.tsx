"use client";

import Link from "next/link";
import { RunStatusBadge } from "@/components/runs/RunStatusBadge";
import { useI18n } from "@/components/common/LocaleProvider";
import { formatDateTime, formatRunMode, formatRunStatus, formatStageName } from "@/lib/i18n";
import type { Run } from "@/lib/types";

type RunTableProps = {
  runs: Run[];
  onCancel: (runId: string) => Promise<void>;
  onDelete: (runId: string) => Promise<void>;
  actionRunId?: string;
  actionKind?: "cancel" | "delete" | null;
  emptyMessage?: string;
};

function summarizeStages(run: Run, locale: "zh" | "en") {
  return run.stages
    .map((stage) => `${formatStageName(stage.stage, locale)}:${formatRunStatus(stage.status, locale)}`)
    .join(" | ");
}

function modeStyle(mode: Run["mode"]): string {
  if (mode === "full_pipeline") {
    return "mode-chip mode-chip-full";
  }
  if (mode === "attack_only") {
    return "mode-chip mode-chip-attack";
  }
  if (mode === "benchmark_only") {
    return "mode-chip mode-chip-benchmark";
  }
  return "mode-chip mode-chip-eval";
}

function renderUpdatedAt(raw: string, locale: "zh" | "en"): string {
  return formatDateTime(raw, locale);
}

export function RunTable({ runs, onCancel, onDelete, actionRunId, actionKind, emptyMessage }: RunTableProps) {
  const { locale } = useI18n();
  const text =
    locale === "zh"
      ? {
          noRuns: "暂无运行记录。",
          name: "名称",
          mode: "模式",
          status: "状态",
          stages: "阶段",
          updated: "更新时间",
          actions: "操作",
          detail: "详情",
          canceling: "取消中...",
          cancel: "取消",
          deleting: "删除中...",
          delete: "删除"
        }
      : {
          noRuns: "No runs yet.",
          name: "Name",
          mode: "Mode",
          status: "Status",
          stages: "Stages",
          updated: "Updated",
          actions: "Actions",
          detail: "Detail",
          canceling: "Canceling...",
          cancel: "Cancel",
          deleting: "Deleting...",
          delete: "Delete"
        };

  if (!runs.length) {
    return <p className="notice p-4 text-sm text-slate-600">{emptyMessage || text.noRuns}</p>;
  }
  return (
    <>
      <div className="space-y-3 md:hidden">
        {runs.map((run) => (
          <article className="section-card space-y-3" key={run.run_id}>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="font-headline text-base font-semibold text-slate-50">{run.name}</p>
                <p className="mono mt-1 break-all text-xs text-slate-400">{run.run_id}</p>
              </div>
              <RunStatusBadge status={run.status} />
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className={modeStyle(run.mode)}>{formatRunMode(run.mode, locale)}</span>
              <span className="text-xs text-slate-400">{renderUpdatedAt(run.updated_at, locale)}</span>
            </div>
            <div>
              <p className="label">{text.stages}</p>
              <p className="mono mt-1 break-words text-xs text-slate-300">{summarizeStages(run, locale) || "-"}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link className="btn flex-1 text-center" href={`/runs/${run.run_id}`}>
                {text.detail}
              </Link>
              {(run.status === "pending" || run.status === "running") && (
                <button
                  className={actionRunId === run.run_id && actionKind === "cancel" ? "btn btn-busy flex-1" : "btn flex-1"}
                  disabled={actionRunId === run.run_id}
                  onClick={() => void onCancel(run.run_id)}
                  type="button"
                >
                  {actionRunId === run.run_id && actionKind === "cancel" ? text.canceling : text.cancel}
                </button>
              )}
              <button
                className={actionRunId === run.run_id && actionKind === "delete" ? "btn btn-busy w-full" : "btn w-full"}
                disabled={actionRunId === run.run_id}
                onClick={() => void onDelete(run.run_id)}
                type="button"
              >
                {actionRunId === run.run_id && actionKind === "delete" ? text.deleting : text.delete}
              </button>
            </div>
          </article>
        ))}
      </div>
      <div className="data-table-wrap hidden md:block">
        <table className="data-table min-w-[920px] bg-transparent">
          <thead>
            <tr>
              <th className="font-semibold">{text.name}</th>
              <th className="font-semibold">{text.mode}</th>
              <th className="font-semibold">{text.status}</th>
              <th className="font-semibold">{text.stages}</th>
              <th className="font-semibold">{text.updated}</th>
              <th className="font-semibold">{text.actions}</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr className="align-top text-sm transition-colors" key={run.run_id}>
                <td>
                  <p className="font-headline font-semibold text-slate-900">{run.name}</p>
                  <p className="mono mt-1 text-xs text-slate-500">{run.run_id}</p>
                </td>
                <td>
                  <span className={modeStyle(run.mode)}>{formatRunMode(run.mode, locale)}</span>
                </td>
                <td>
                  <RunStatusBadge status={run.status} />
                </td>
                <td>
                  <p className="mono text-xs text-slate-700">{summarizeStages(run, locale) || "-"}</p>
                </td>
                <td>
                  <p className="text-slate-700">{renderUpdatedAt(run.updated_at, locale)}</p>
                </td>
                <td>
                  <div className="flex items-center gap-2">
                    <Link className="btn" href={`/runs/${run.run_id}`}>
                      {text.detail}
                    </Link>
                    {(run.status === "pending" || run.status === "running") && (
                      <button
                        className={actionRunId === run.run_id && actionKind === "cancel" ? "btn btn-busy" : "btn"}
                        disabled={actionRunId === run.run_id}
                        onClick={() => void onCancel(run.run_id)}
                        type="button"
                      >
                        {actionRunId === run.run_id && actionKind === "cancel" ? text.canceling : text.cancel}
                      </button>
                    )}
                    <button
                      className={actionRunId === run.run_id && actionKind === "delete" ? "btn btn-busy" : "btn"}
                      disabled={actionRunId === run.run_id}
                      onClick={() => void onDelete(run.run_id)}
                      type="button"
                    >
                      {actionRunId === run.run_id && actionKind === "delete" ? text.deleting : text.delete}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
