import type { Artifact } from "@/lib/types";

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
  if (!artifacts.length) {
    return <p className="notice text-slate-600">No artifacts recorded yet.</p>;
  }
  return (
    <div className="data-table-wrap">
      <table className="data-table min-w-[860px]">
        <thead>
          <tr>
            <th className="font-semibold">Type</th>
            <th className="font-semibold">Stage</th>
            <th className="font-semibold">Path</th>
            <th className="font-semibold">Size</th>
            <th className="font-semibold">Created</th>
          </tr>
        </thead>
        <tbody>
          {artifacts.map((item) => (
            <tr className="text-sm transition-colors" key={item.artifact_id}>
              <td className="text-slate-700">{item.type}</td>
              <td className="text-slate-700">{item.stage}</td>
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
