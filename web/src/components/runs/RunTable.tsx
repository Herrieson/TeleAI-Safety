import Link from "next/link";
import { RunStatusBadge } from "@/components/runs/RunStatusBadge";
import type { Run } from "@/lib/types";

type RunTableProps = {
  runs: Run[];
  onCancel: (runId: string) => Promise<void>;
  onDelete: (runId: string) => Promise<void>;
  actionRunId?: string;
  actionKind?: "cancel" | "delete" | null;
  emptyMessage?: string;
};

function summarizeStages(run: Run) {
  return run.stages.map((stage) => `${stage.stage}:${stage.status}`).join(" | ");
}

function renderUpdatedAt(raw: string): string {
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) {
    return raw;
  }
  return date.toLocaleString();
}

export function RunTable({ runs, onCancel, onDelete, actionRunId, actionKind, emptyMessage }: RunTableProps) {
  if (!runs.length) {
    return <p className="notice p-4 text-sm text-slate-600">{emptyMessage || "No runs yet."}</p>;
  }
  return (
    <div className="data-table-wrap">
      <table className="data-table min-w-[920px] bg-transparent">
        <thead>
          <tr>
            <th className="font-semibold">Name</th>
            <th className="font-semibold">Mode</th>
            <th className="font-semibold">Status</th>
            <th className="font-semibold">Stages</th>
            <th className="font-semibold">Updated</th>
            <th className="font-semibold">Actions</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr className="align-top text-sm transition-colors" key={run.run_id}>
              <td>
                <p className="font-headline font-semibold text-slate-900">{run.name}</p>
                <p className="mono mt-1 text-xs text-slate-500">{run.run_id}</p>
              </td>
              <td className="text-slate-700">{run.mode}</td>
              <td>
                <RunStatusBadge status={run.status} />
              </td>
              <td>
                <p className="mono text-xs text-slate-700">{summarizeStages(run) || "-"}</p>
              </td>
              <td>
                <p className="text-slate-700">{renderUpdatedAt(run.updated_at)}</p>
              </td>
              <td>
                <div className="flex items-center gap-2">
                  <Link className="btn" href={`/runs/${run.run_id}`}>
                    Detail
                  </Link>
                  {(run.status === "pending" || run.status === "running") && (
                    <button
                      className={actionRunId === run.run_id && actionKind === "cancel" ? "btn btn-busy" : "btn"}
                      disabled={actionRunId === run.run_id}
                      onClick={() => void onCancel(run.run_id)}
                      type="button"
                    >
                      {actionRunId === run.run_id && actionKind === "cancel" ? "Canceling..." : "Cancel"}
                    </button>
                  )}
                  <button
                    className={actionRunId === run.run_id && actionKind === "delete" ? "btn btn-busy" : "btn"}
                    disabled={actionRunId === run.run_id}
                    onClick={() => void onDelete(run.run_id)}
                    type="button"
                  >
                    {actionRunId === run.run_id && actionKind === "delete" ? "Deleting..." : "Delete"}
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
