import type { RunStage } from "@/lib/types";
import { RunStatusBadge } from "@/components/runs/RunStatusBadge";

export function StageTimeline({ stages }: { stages: RunStage[] }) {
  if (!stages.length) {
    return <p className="text-sm text-slate-600">No stage records.</p>;
  }
  return (
    <ul className="space-y-3">
      {stages.map((stage) => (
        <li
          className="rounded-2xl border border-[#d7e5f2] bg-[linear-gradient(150deg,rgba(255,255,255,0.95),rgba(241,248,255,0.9))] px-4 py-3 shadow-[0_8px_18px_rgba(12,46,79,0.08)]"
          key={`${stage.stage}-${stage.updated_at}-${stage.status}`}
        >
          <div className="mb-2 flex items-center justify-between">
            <p className="font-headline text-base font-semibold capitalize">{stage.stage}</p>
            <RunStatusBadge status={stage.status} />
          </div>
          <div className="grid grid-cols-1 gap-1 text-sm text-slate-700 md:grid-cols-2">
            <p>
              <span className="label mr-2">Start</span>
              {stage.started_at || "-"}
            </p>
            <p>
              <span className="label mr-2">End</span>
              {stage.ended_at || "-"}
            </p>
            <p>
              <span className="label mr-2">Exit</span>
              {stage.exit_code === null ? "-" : stage.exit_code}
            </p>
            <p className="truncate">
              <span className="label mr-2">Log</span>
              <span className="mono text-xs">{stage.log_path || "-"}</span>
            </p>
          </div>
          {stage.error ? <p className="mt-2 text-sm text-rose-700">{stage.error}</p> : null}
        </li>
      ))}
    </ul>
  );
}
