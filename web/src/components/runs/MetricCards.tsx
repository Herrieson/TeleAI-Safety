type MetricCardsProps = {
  summary: Record<string, unknown>;
  emptyMessage?: string;
};

function asScore(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) {
    if (value >= 0 && value <= 1) {
      return `${(value * 100).toFixed(2)}%`;
    }
    return value.toFixed(4);
  }
  return "-";
}

export function MetricCards({ summary, emptyMessage }: MetricCardsProps) {
  if (!summary || Object.keys(summary).length === 0) {
    return <p className="notice text-slate-600">{emptyMessage || "No metric summary generated yet."}</p>;
  }
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
      <article className="stat-card">
        <p className="label mb-1">ASR Avg</p>
        <p className="font-headline text-2xl font-semibold text-[#0d65b3]">{asScore(summary.asr_avg)}</p>
      </article>
      <article className="stat-card">
        <p className="label mb-1">ASR Effective Avg</p>
        <p className="font-headline text-2xl font-semibold text-[#0b8f69]">{asScore(summary.asr_effective_avg)}</p>
      </article>
      <article className="stat-card">
        <p className="label mb-1">FRR Avg</p>
        <p className="font-headline text-2xl font-semibold text-[#b36a20]">{asScore(summary.frr_avg)}</p>
      </article>
      <article className="stat-card md:col-span-3">
        <p className="label mb-1">Scorers</p>
        <p className="mono text-sm text-slate-700">
          {Array.isArray(summary.scorers) ? summary.scorers.join(", ") : "-"}
        </p>
      </article>
    </div>
  );
}
