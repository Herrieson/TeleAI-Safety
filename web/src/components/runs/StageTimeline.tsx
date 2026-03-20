import type { RunStage } from "@/lib/types";
import { RunStatusBadge } from "@/components/runs/RunStatusBadge";

export function StageTimeline({ stages }: { stages: RunStage[] }) {
  if (!stages.length) {
    return <p className="text-sm text-slate-600">No stage records.</p>;
  }
  return (
    <ul className="stage-list reveal-grid">
      {stages.map((stage, index) => (
        <li className="stage-item" key={`${stage.stage}-${stage.updated_at}-${stage.status}`}>
          <div className="mb-2 flex items-center justify-between gap-3">
            <div>
              <p className="label mb-1">Stage {index + 1}</p>
              <p className="font-headline text-base font-semibold capitalize">{stage.stage}</p>
            </div>
            <RunStatusBadge status={stage.status} />
          </div>
          <div className="timeline-meta">
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
          {stage.command ? (
            <p className="tech-subpanel mt-2 truncate px-2 py-1.5 mono text-[11px] text-slate-700">
              {stage.command}
            </p>
          ) : null}
          {stage.error ? <p className="notice notice-error mt-2">{stage.error}</p> : null}
        </li>
      ))}
    </ul>
  );
}
