"use client";

import { useEffect, useMemo, useState } from "react";

type AnimatedNumberProps = {
  value: number;
  durationMs?: number;
  decimals?: number;
  suffix?: string;
  className?: string;
};

function formatNumber(value: number, decimals: number): string {
  const rounded = Number(value.toFixed(decimals));
  return rounded.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  });
}

export function AnimatedNumber({
  value,
  durationMs = 520,
  decimals = 0,
  suffix = "",
  className = ""
}: AnimatedNumberProps) {
  const [displayValue, setDisplayValue] = useState(value);

  useEffect(() => {
    const from = displayValue;
    const to = value;
    if (!Number.isFinite(from) || !Number.isFinite(to) || from === to) {
      setDisplayValue(to);
      return;
    }

    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (media.matches) {
      setDisplayValue(to);
      return;
    }

    const start = performance.now();
    let frame = 0;

    function tick(now: number) {
      const elapsed = now - start;
      const progress = Math.min(1, elapsed / durationMs);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayValue(from + (to - from) * eased);
      if (progress < 1) {
        frame = window.requestAnimationFrame(tick);
      }
    }

    frame = window.requestAnimationFrame(tick);
    return () => {
      window.cancelAnimationFrame(frame);
    };
  }, [durationMs, value]);

  const rendered = useMemo(() => formatNumber(displayValue, decimals), [decimals, displayValue]);

  return <span className={className}>{rendered}{suffix}</span>;
}
