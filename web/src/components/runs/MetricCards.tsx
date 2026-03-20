import { AnimatedNumber } from "@/components/common/AnimatedNumber";

type MetricCardsProps = {
  summary: Record<string, unknown>;
  emptyMessage?: string;
};

function scoreDisplay(value: unknown): { value: number; decimals: number; suffix: string; fallback: string } {
  if (typeof value === "number" && Number.isFinite(value)) {
    if (value >= 0 && value <= 1) {
      return { value: value * 100, decimals: 2, suffix: "%", fallback: "-" };
    }
    return { value, decimals: 4, suffix: "", fallback: "-" };
  }
  return { value: 0, decimals: 2, suffix: "", fallback: "-" };
}

export function MetricCards({ summary, emptyMessage }: MetricCardsProps) {
  if (!summary || Object.keys(summary).length === 0) {
    return <p className="notice text-slate-600">{emptyMessage || "No metric summary generated yet."}</p>;
  }
  const asr = scoreDisplay(summary.asr_avg);
  const asrEffective = scoreDisplay(summary.asr_effective_avg);
  const frr = scoreDisplay(summary.frr_avg);

  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-3 reveal-grid">
      <article className="stat-card">
        <p className="label mb-1">ASR Avg</p>
        <p className="font-headline text-2xl font-semibold text-[#0d65b3]">
          {typeof summary.asr_avg === "number" && Number.isFinite(summary.asr_avg) ? (
            <AnimatedNumber decimals={asr.decimals} suffix={asr.suffix} value={asr.value} />
          ) : (
            asr.fallback
          )}
        </p>
      </article>
      <article className="stat-card">
        <p className="label mb-1">ASR Effective Avg</p>
        <p className="font-headline text-2xl font-semibold text-[#0b8f69]">
          {typeof summary.asr_effective_avg === "number" && Number.isFinite(summary.asr_effective_avg) ? (
            <AnimatedNumber decimals={asrEffective.decimals} suffix={asrEffective.suffix} value={asrEffective.value} />
          ) : (
            asrEffective.fallback
          )}
        </p>
      </article>
      <article className="stat-card">
        <p className="label mb-1">FRR Avg</p>
        <p className="font-headline text-2xl font-semibold text-[#b36a20]">
          {typeof summary.frr_avg === "number" && Number.isFinite(summary.frr_avg) ? (
            <AnimatedNumber decimals={frr.decimals} suffix={frr.suffix} value={frr.value} />
          ) : (
            "Not generated"
          )}
        </p>
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
