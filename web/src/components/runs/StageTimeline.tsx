"use client";

import type { RunStage } from "@/lib/types";
import { formatStageName } from "@/lib/i18n";
import { RunStatusBadge } from "@/components/runs/RunStatusBadge";
import { useI18n } from "@/components/common/LocaleProvider";

export function StageTimeline({ stages }: { stages: RunStage[] }) {
  const { locale } = useI18n();
  const text =
    locale === "zh"
      ? {
          empty: "暂无阶段记录。",
          stage: "阶段",
          start: "开始",
          end: "结束",
          exit: "退出码",
          log: "日志"
        }
      : {
          empty: "No stage records.",
          stage: "Stage",
          start: "Start",
          end: "End",
          exit: "Exit",
          log: "Log"
        };

  if (!stages.length) {
    return <p className="text-sm text-slate-600">{text.empty}</p>;
  }

  return (
    <ul className="stage-list reveal-grid">
      {stages.map((stage, index) => (
        <li className="stage-item" key={`${stage.stage}-${stage.updated_at}-${stage.status}`}>
          <div className="mb-2 flex items-center justify-between gap-3">
            <div>
              <p className="label mb-1">{text.stage} {index + 1}</p>
              <p className="font-headline text-base font-semibold capitalize">{formatStageName(stage.stage, locale)}</p>
            </div>
            <RunStatusBadge status={stage.status} />
          </div>
          <div className="timeline-meta">
            <p>
              <span className="label mr-2">{text.start}</span>
              {stage.started_at || "-"}
            </p>
            <p>
              <span className="label mr-2">{text.end}</span>
              {stage.ended_at || "-"}
            </p>
            <p>
              <span className="label mr-2">{text.exit}</span>
              {stage.exit_code === null ? "-" : stage.exit_code}
            </p>
            <p className="truncate">
              <span className="label mr-2">{text.log}</span>
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
