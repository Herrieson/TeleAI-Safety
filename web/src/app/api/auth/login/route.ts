import { NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE_NAME } from "@/lib/auth";
import { getBffBaseUrl } from "@/lib/server/bff";

type ParsedJson = Record<string, unknown>;

type UpstreamLoginResponse = {
  token: string;
  session_ttl_seconds: number | string;
  user: unknown;
};

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

function isUpstreamLoginResponse(data: ParsedJson): data is ParsedJson & UpstreamLoginResponse {
  return typeof data.token === "string" && "session_ttl_seconds" in data && "user" in data;
}

export async function POST(request: NextRequest) {
  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ detail: "invalid json payload" }, { status: 400 });
  }

  const upstream = await fetch(`${getBffBaseUrl()}/api/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload),
    cache: "no-store"
  });

  const raw = await upstream.text();
  const data = parseJsonSafely(raw);
  if (!upstream.ok) {
    return NextResponse.json({ detail: data.detail || "login failed" }, { status: upstream.status });
  }
  if (!isUpstreamLoginResponse(data)) {
    return NextResponse.json({ detail: "invalid upstream login response" }, { status: 502 });
  }

  const response = NextResponse.json({
    user: data.user
  });
  response.cookies.set(SESSION_COOKIE_NAME, data.token, {
    httpOnly: true,
    maxAge: Number(data.session_ttl_seconds) || 43200,
    path: "/",
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production"
  });
  return response;
}
