import { NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE_NAME } from "@/lib/auth";
import { getBffBaseUrl } from "@/lib/server/bff";

function parseJsonSafely(raw: string): Record<string, unknown> {
  if (!raw) {
    return {};
  }
  try {
    return JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return { detail: raw };
  }
}

export async function GET(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  if (!token) {
    return NextResponse.json({ detail: "authentication required" }, { status: 401 });
  }

  const upstream = await fetch(`${getBffBaseUrl()}/api/auth/me`, {
    headers: {
      Authorization: `Bearer ${token}`
    },
    cache: "no-store"
  });

  const raw = await upstream.text();
  const data = parseJsonSafely(raw);
  if (!upstream.ok) {
    return NextResponse.json({ detail: data.detail || "authentication required" }, { status: upstream.status });
  }
  return NextResponse.json(data);
}
