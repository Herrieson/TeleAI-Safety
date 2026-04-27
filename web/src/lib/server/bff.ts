import "server-only";

export function getBffBaseUrl(): string {
  return (process.env.BFF_BASE_URL || process.env.NEXT_PUBLIC_BFF_BASE_URL || "http://127.0.0.1:9000").replace(/\/+$/, "");
}
