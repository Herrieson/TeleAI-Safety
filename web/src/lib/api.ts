import type {
  AttackConfigOptionsResponse,
  BenchmarkConfigOptionsResponse,
  LeaderboardResponse,
  QuickAttackDatasetsResponse,
  QuickAttackMethodsResponse,
  Run,
  RunArtifactsResponse,
  RunCreatePayload,
  RunLogsResponse,
  RunMetricTaskReportResponse,
  RunMetricsSummaryResponse,
  RunMetricTasksResponse
} from "@/lib/types";

const BASE_URL = (process.env.NEXT_PUBLIC_BFF_BASE_URL || "http://127.0.0.1:9000").replace(/\/+$/, "");

class ApiError extends Error {
  statusCode: number;

  constructor(message: string, statusCode: number) {
    super(message);
    this.statusCode = statusCode;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {})
    },
    cache: "no-store"
  });
  if (!response.ok) {
    const raw = await response.text();
    throw new ApiError(raw || `Request failed: ${response.status}`, response.status);
  }
  if (response.status === 204) {
    return {} as T;
  }
  return (await response.json()) as T;
}

export function getRuns() {
  return request<Run[]>("/api/runs");
}

export function getRun(runId: string) {
  return request<Run>(`/api/runs/${runId}`);
}

export function createRun(payload: RunCreatePayload) {
  return request<Run>("/api/runs", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function cancelRun(runId: string) {
  return request<Run>(`/api/runs/${runId}/cancel`, {
    method: "POST"
  });
}

export function deleteRun(runId: string) {
  return request<{ run_id: string; deleted: boolean }>(`/api/runs/${runId}`, {
    method: "DELETE"
  });
}

export function getRunLogs(runId: string, stage: string, tailLines: number) {
  const encodedStage = encodeURIComponent(stage);
  return request<RunLogsResponse>(
    `/api/runs/${runId}/logs?stage=${encodedStage}&tail_lines=${encodeURIComponent(String(tailLines))}`
  );
}

export function getRunArtifacts(runId: string) {
  return request<RunArtifactsResponse>(`/api/runs/${runId}/artifacts`);
}

export function getRunMetricsSummary(runId: string) {
  return request<RunMetricsSummaryResponse>(`/api/runs/${runId}/metrics/summary`);
}

export function getRunMetricTasks(runId: string) {
  return request<RunMetricTasksResponse>(`/api/runs/${runId}/metrics/tasks`);
}

export function exportRunMetricTaskReport(runId: string, taskId: string) {
  const encodedTaskId = encodeURIComponent(taskId);
  return request<RunMetricTaskReportResponse>(`/api/runs/${runId}/metrics/tasks/${encodedTaskId}/report`);
}

export function getQuickAttackMethods() {
  return request<QuickAttackMethodsResponse>("/api/quick-attack/methods");
}

export function getQuickAttackDatasets() {
  return request<QuickAttackDatasetsResponse>("/api/quick-attack/datasets");
}

export function getAttackConfigOptions() {
  return request<AttackConfigOptionsResponse>("/api/attack/config-options");
}

export function getBenchmarkConfigOptions() {
  return request<BenchmarkConfigOptionsResponse>("/api/benchmark/config-options");
}

export function getLeaderboard() {
  return request<LeaderboardResponse>("/api/leaderboard");
}

export { ApiError };
