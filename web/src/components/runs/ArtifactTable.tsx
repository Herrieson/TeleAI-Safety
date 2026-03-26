"use client";

import type { Artifact } from "@/lib/types";
import { formatStageName } from "@/lib/i18n";
import { useI18n } from "@/components/common/LocaleProvider";

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) {
    return "-";
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(value >= 10 ? 1 : 2)} ${units[unitIndex]}`;
}

export function ArtifactTable({ artifacts }: { artifacts: Artifact[] }) {
  const { locale } = useI18n();
  const text =
    locale === "zh"
      ? {
          empty: "暂无产物记录。",
          type: "类型",
          stage: "阶段",
          path: "路径",
          size: "大小",
          created: "创建时间"
        }
      : {
          empty: "No artifacts recorded yet.",
          type: "Type",
          stage: "Stage",
          path: "Path",
          size: "Size",
          created: "Created"
        };

  if (!artifacts.length) {
    return <p className="notice text-slate-600">{text.empty}</p>;
  }
  return (
    <div className="data-table-wrap">
      <table className="data-table min-w-[860px]">
        <thead>
          <tr>
            <th className="font-semibold">{text.type}</th>
            <th className="font-semibold">{text.stage}</th>
            <th className="font-semibold">{text.path}</th>
            <th className="font-semibold">{text.size}</th>
            <th className="font-semibold">{text.created}</th>
          </tr>
        </thead>
        <tbody>
          {artifacts.map((item) => (
            <tr className="text-sm transition-colors" key={item.artifact_id}>
              <td className="text-slate-700">{item.type}</td>
              <td className="text-slate-700">{formatStageName(item.stage, locale)}</td>
              <td>
                <span className="mono text-xs text-slate-700">{item.path}</span>
              </td>
              <td className="text-slate-700">{formatBytes(item.size_bytes)}</td>
              <td className="text-slate-700">{item.created_at}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
