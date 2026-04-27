"use client";

import type { Dispatch, SetStateAction } from "react";
import type { NewRunText } from "@/lib/newRunText";
import type { ManagedModePolicy, ManagedTargetModel, RunCreatePayload } from "@/lib/types";

type ManagedModeFormProps = {
  text: NewRunText;
  payload: RunCreatePayload;
  setPayload: Dispatch<SetStateAction<RunCreatePayload>>;
  managedTargetModels: ManagedTargetModel[];
  selectedManagedModel: ManagedTargetModel | null;
  managedPolicy: ManagedModePolicy | null;
  managedInviteCodeRequired: boolean;
  autoStageSummary: string;
  error: string;
  initializing: boolean;
  submitting: boolean;
  onReset: () => void;
};

export function ManagedModeForm({
  text,
  payload,
  setPayload,
  managedTargetModels,
  selectedManagedModel,
  managedPolicy,
  managedInviteCodeRequired,
  autoStageSummary,
  error,
  initializing,
  submitting,
  onReset
}: ManagedModeFormProps) {
  return (
    <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
      <div className="space-y-5 xl:col-span-8 reveal-grid">
        <article className="section-card" data-tour="managed-main-form">
          <p className="label mb-3">{text.managedModeTitle}</p>
          <p className="mb-4 text-sm text-slate-600">{text.managedModeDesc}</p>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <label>
              <span className="label mb-1 block">{text.runNameOptional}</span>
              <input
                className="input"
                onChange={(event) => setPayload((prev) => ({ ...prev, name: event.target.value }))}
                placeholder="e.g. managed-gpt54-nightly"
                value={payload.name}
              />
            </label>
            <label>
              <span className="label mb-1 block">{text.managedTargetModel}</span>
              <select
                className="select"
                onChange={(event) => {
                  const model = managedTargetModels.find((item) => item.id === event.target.value) || null;
                  setPayload((prev) => ({
                    ...prev,
                    managed_target_model_id: event.target.value,
                    quick_target_model_name: model?.target_model_name || prev.quick_target_model_name
                  }));
                }}
                value={payload.managed_target_model_id || ""}
              >
                <option value="">{managedTargetModels.length ? text.managedSelectPlaceholder : text.managedNoModels}</option>
                {managedTargetModels.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
              {selectedManagedModel?.description ? (
                <p className="mt-1 text-xs text-slate-600">{selectedManagedModel.description}</p>
              ) : null}
            </label>
            {managedPolicy?.access_control_enabled ? (
              <label className="md:col-span-2">
                <span className="label mb-1 block">{text.managedAccessCode}</span>
                <input
                  className="input mono"
                  onChange={(event) => setPayload((prev) => ({ ...prev, managed_access_code: event.target.value }))}
                  placeholder={managedInviteCodeRequired ? "required-invite-code" : "optional-invite-code"}
                  value={payload.managed_access_code || ""}
                />
                <p className="mt-1 text-xs text-slate-600">{text.managedAccessCodeHint}</p>
              </label>
            ) : null}
          </div>
          {managedPolicy ? (
            <p className="tech-subpanel mt-4 p-3 text-sm text-slate-700">
              {text.managedPolicyHint(
                managedPolicy.max_active_runs_global,
                managedPolicy.max_active_runs_per_ip,
                managedPolicy.min_interval_seconds
              )}
            </p>
          ) : null}
        </article>

        {error ? (
          <p aria-live="assertive" className="notice notice-error" role="alert">
            {error}
          </p>
        ) : null}

        <div className="flex flex-wrap items-center gap-2">
          <button
            className={submitting ? "btn btn-primary btn-busy" : "btn btn-primary"}
            data-tour="managed-submit"
            disabled={submitting || initializing || !managedTargetModels.length || (managedInviteCodeRequired && !(payload.managed_access_code || "").trim())}
            type="submit"
          >
            {submitting ? text.submitting : initializing ? text.preparing : text.simpleSubmit}
          </button>
          <button className="btn" onClick={onReset} type="button">
            {text.reset}
          </button>
        </div>
      </div>

      <aside className="space-y-4 xl:col-span-4 xl:sticky xl:top-6 xl:self-start reveal-grid">
        <article className="stat-card">
          <p className="label mb-2">{text.autoRunSummaryTitle}</p>
          <p className="mb-4 text-sm text-slate-600">{text.autoRunSummaryManagedDesc}</p>
          <dl className="space-y-3 text-sm text-slate-700">
            <div>
              <dt className="label">{text.autoRunSummaryStages}</dt>
              <dd className="mono text-xs">{autoStageSummary}</dd>
            </div>
            <div>
              <dt className="label">{text.autoRunSummaryTarget}</dt>
              <dd>{selectedManagedModel?.target_model_name || "-"}</dd>
            </div>
          </dl>
          <p className="notice notice-good mt-4 text-sm">{text.autoRunSummaryMonitor}</p>
        </article>

        <article className="stat-card">
          <p className="label mb-2">{text.managedSummaryTitle}</p>
          <p className="text-sm text-slate-600">{text.managedSummaryDesc}</p>
        </article>
      </aside>
    </div>
  );
}
