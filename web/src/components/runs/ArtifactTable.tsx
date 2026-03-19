import type { Artifact } from "@/lib/types";

export function ArtifactTable({ artifacts }: { artifacts: Artifact[] }) {
  if (!artifacts.length) {
    return <p className="text-sm text-slate-600">No artifacts recorded yet.</p>;
  }
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white/90">
      <table className="w-full min-w-[860px] border-collapse">
        <thead>
          <tr className="bg-slate-50/90 text-left text-xs uppercase tracking-[0.08em] text-slate-600">
            <th className="border-b border-slate-200 px-3 py-2 font-semibold">Type</th>
            <th className="border-b border-slate-200 px-3 py-2 font-semibold">Stage</th>
            <th className="border-b border-slate-200 px-3 py-2 font-semibold">Path</th>
            <th className="border-b border-slate-200 px-3 py-2 font-semibold">Size</th>
            <th className="border-b border-slate-200 px-3 py-2 font-semibold">Created</th>
          </tr>
        </thead>
        <tbody>
          {artifacts.map((item) => (
            <tr className="text-sm transition-colors hover:bg-slate-50/70" key={item.artifact_id}>
              <td className="border-b border-slate-100 px-3 py-2 text-slate-700">{item.type}</td>
              <td className="border-b border-slate-100 px-3 py-2 text-slate-700">{item.stage}</td>
              <td className="border-b border-slate-100 px-3 py-2">
                <span className="mono text-xs text-slate-700">{item.path}</span>
              </td>
              <td className="border-b border-slate-100 px-3 py-2 text-slate-700">{item.size_bytes}</td>
              <td className="border-b border-slate-100 px-3 py-2 text-slate-700">{item.created_at}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
