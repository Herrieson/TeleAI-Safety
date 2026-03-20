import Link from "next/link";
import { RunStatusBadge } from "@/components/runs/RunStatusBadge";
import type { Run } from "@/lib/types";

type RunTableProps = {
  runs: Run[];
  onCancel: (runId: string) => Promise<void>;
  onDelete: (runId: string) => Promise<void>;
};

function summarizeStages(run: Run) {
  return run.stages.map((stage) => `${stage.stage}:${stage.status}`).join(" | ");
}

export function RunTable({ runs, onCancel, onDelete }: RunTableProps) {
  if (!runs.length) {
    return <p className="p-4 text-sm text-slate-600">No runs yet.</p>;
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
                <p className="text-slate-700">{run.updated_at}</p>
              </td>
              <td>
                <div className="flex items-center gap-2">
                  <Link className="btn" href={`/runs/${run.run_id}`}>
                    Detail
                  </Link>
                  {(run.status === "pending" || run.status === "running") && (
                    <button className="btn" onClick={() => onCancel(run.run_id)} type="button">
                      Cancel
                    </button>
                  )}
                  <button className="btn" onClick={() => onDelete(run.run_id)} type="button">
                    Delete
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
