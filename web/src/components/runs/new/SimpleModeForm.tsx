"use client";

import type { Dispatch, SetStateAction } from "react";
import type { NewRunText } from "@/lib/newRunText";
import type { RunCreatePayload } from "@/lib/types";

type SimpleModeFormProps = {
  text: NewRunText;
  payload: RunCreatePayload;
  setPayload: Dispatch<SetStateAction<RunCreatePayload>>;
  autoStageSummary: string;
  error: string;
  initializing: boolean;
  submitting: boolean;
  onReset: () => void;
};

export function SimpleModeForm({
  text,
  payload,
  setPayload,
  autoStageSummary,
  error,
  initializing,
  submitting,
  onReset
}: SimpleModeFormProps) {
  return (
    <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
      <div className="space-y-5 xl:col-span-8 reveal-grid">
        <article className="section-card" data-tour="simple-main-form">
          <p className="label mb-3">{text.simpleModeTitle}</p>
          <p className="mb-4 text-sm text-slate-600">{text.simpleModeDesc}</p>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <label>
              <span className="label mb-1 block">{text.targetModelName}</span>
              <input
                className="input"
                onChange={(event) =>
                  setPayload((prev) => ({
                    ...prev,
                    quick_target_model_name: event.target.value
                  }))
                }
                placeholder="gpt-4o-mini"
                value={payload.quick_target_model_name}
              />
            </label>
            <label>
              <span className="label mb-1 block">{text.openaiBaseUrl}</span>
              <input
                className="input mono"
                onChange={(event) =>
                  setPayload((prev) => ({
                    ...prev,
                    quick_openai_base_url: event.target.value
                  }))
                }
                placeholder="https://api.openai.com/v1"
                value={payload.quick_openai_base_url}
              />
            </label>
            <label>
              <span className="label mb-1 block">{text.openaiApiKey}</span>
              <input
                className="input mono"
                onChange={(event) =>
                  setPayload((prev) => ({
                    ...prev,
                    quick_openai_api_key: event.target.value
                  }))
                }
                placeholder="sk-..."
                type="password"
                value={payload.quick_openai_api_key}
              />
            </label>
          </div>
        </article>

        {error ? (
          <p aria-live="assertive" className="notice notice-error" role="alert">
            {error}
          </p>
        ) : null}

        <div className="flex flex-wrap items-center gap-2">
          <button
            className={submitting ? "btn btn-primary btn-busy" : "btn btn-primary"}
            data-tour="simple-submit"
            disabled={submitting || initializing}
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
          <p className="mb-4 text-sm text-slate-600">{text.autoRunSummaryDesc}</p>
          <dl className="space-y-3 text-sm text-slate-700">
            <div>
              <dt className="label">{text.autoRunSummaryStages}</dt>
              <dd className="mono text-xs">{autoStageSummary}</dd>
            </div>
            <div>
              <dt className="label">{text.autoRunSummaryTarget}</dt>
              <dd>{payload.quick_target_model_name || "-"}</dd>
            </div>
          </dl>
          <p className="notice notice-good mt-4 text-sm">{text.autoRunSummaryMonitor}</p>
        </article>
      </aside>
    </div>
  );
}
