import type { RunStatus } from "@/lib/types";

const statusStyleMap: Record<RunStatus, string> = {
  pending: "bg-slate-100/90 text-slate-700 border-slate-300",
  running: "bg-cyan-50/95 text-cyan-700 border-cyan-300",
  succeeded: "bg-emerald-50/95 text-emerald-700 border-emerald-300",
  failed: "bg-rose-50/95 text-rose-700 border-rose-300",
  canceled: "bg-amber-50/95 text-amber-700 border-amber-300"
};

export function RunStatusBadge({ status }: { status: RunStatus }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-xs font-medium uppercase tracking-[0.06em] shadow-sm ${statusStyleMap[status]}`}
    >
      <span className="inline-block h-1.5 w-1.5 rounded-full bg-current opacity-80" />
      {status}
    </span>
  );
}
