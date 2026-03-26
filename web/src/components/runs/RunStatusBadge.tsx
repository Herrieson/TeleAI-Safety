"use client";

import type { RunStatus } from "@/lib/types";
import { formatRunStatus } from "@/lib/i18n";
import { useI18n } from "@/components/common/LocaleProvider";

const statusStyleMap: Record<RunStatus, string> = {
  pending: "bg-slate-900/70 text-slate-200 border-slate-600",
  running: "bg-cyan-900/45 text-cyan-200 border-cyan-500/70 shadow-[0_6px_14px_rgba(24,132,183,0.28)]",
  succeeded: "bg-emerald-900/45 text-emerald-200 border-emerald-500/70",
  failed: "bg-rose-900/45 text-rose-200 border-rose-500/70",
  canceled: "bg-amber-900/45 text-amber-200 border-amber-500/70"
};

export function RunStatusBadge({ status }: { status: RunStatus }) {
  const { locale } = useI18n();

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[11px] font-semibold uppercase tracking-[0.08em] shadow-sm ${statusStyleMap[status]}`}
    >
      <span className="inline-block h-1.5 w-1.5 rounded-full bg-current opacity-80" />
      {formatRunStatus(status, locale)}
    </span>
  );
}
