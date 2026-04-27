import type {
  AttackConfigOptionsResponse,
  AuthUser,
  BenchmarkConfigOptionsResponse,
  LoginPayload,
  LoginResponse,
  MechanismLeaderboardResponse,
  MechanismOverviewResponse,
  LeaderboardResponse,
  ManagedTargetModelsResponse,
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

class ApiError extends Error {
  statusCode: number;

  constructor(message: string, statusCode: number) {
    super(message);
    this.statusCode = statusCode;
  }
}

function parseErrorMessage(raw: string): string {
  if (!raw) {
    return "";
  }
  try {
    const parsed = JSON.parse(raw) as { detail?: unknown };
    if (typeof parsed.detail === "string" && parsed.detail.trim()) {
      return parsed.detail;
    }
  } catch {
    return raw;
  }
  return raw;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...options,
    headers: {
      ...(options?.body ? { "Content-Type": "application/json" } : {}),
      ...(options?.headers || {})
    },
    cache: "no-store"
  });
  if (!response.ok) {
    const raw = await response.text();
    throw new ApiError(parseErrorMessage(raw) || `Request failed: ${response.status}`, response.status);
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

export function getManagedTargetModels() {
  return request<ManagedTargetModelsResponse>("/api/managed-target-models");
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

export function getMechanismOverview() {
  return request<MechanismOverviewResponse>("/api/mechanism/overview");
}

export function getMechanismLeaderboard() {
  return request<MechanismLeaderboardResponse>("/api/mechanism/leaderboard");
}

export function getMechanismDashboardUrl() {
  return "/api/mechanism/dashboard";
}

export function login(payload: LoginPayload) {
  return request<LoginResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function logout() {
  return request<{ ok: true }>("/api/auth/logout", {
    method: "POST"
  });
}

export function getCurrentUser() {
  return request<AuthUser>("/api/auth/me");
}

export { ApiError };
