"use client";

import type { NewRunViewMode } from "@/lib/newRunConfig";

type RunModeSwitcherProps = {
  mode: NewRunViewMode;
  onChange: (nextMode: NewRunViewMode) => void;
  labels: {
    simple: string;
    managed: string;
    advanced: string;
  };
};

export function RunModeSwitcher({ mode, onChange, labels }: RunModeSwitcherProps) {
  const items: Array<{ value: NewRunViewMode; label: string }> = [
    { value: "simple", label: labels.simple },
    { value: "managed", label: labels.managed },
    { value: "advanced", label: labels.advanced }
  ];

  return (
    <div className="mode-switcher mb-5">
      {items.map((item) => (
        <button
          className={mode === item.value ? "btn btn-primary" : "btn"}
          key={item.value}
          onClick={() => onChange(item.value)}
          type="button"
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
