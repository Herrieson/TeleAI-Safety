import { NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE_NAME } from "@/lib/auth";
import { getBffBaseUrl } from "@/lib/server/bff";

type RouteContext = {
  params: {
    path: string[];
  };
};

async function proxyToBff(request: NextRequest, context: RouteContext) {
  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  if (!token) {
    return NextResponse.json({ detail: "authentication required" }, { status: 401 });
  }

  const upstreamUrl = new URL(`${getBffBaseUrl()}/api/${context.params.path.join("/")}`);
  upstreamUrl.search = request.nextUrl.search;

  const headers = new Headers();
  const accept = request.headers.get("accept");
  const contentType = request.headers.get("content-type");
  if (accept) {
    headers.set("accept", accept);
  }
  if (contentType) {
    headers.set("content-type", contentType);
  }
  headers.set("authorization", `Bearer ${token}`);

  const upstream = await fetch(upstreamUrl, {
    method: request.method,
    headers,
    body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer(),
    cache: "no-store",
    redirect: "manual"
  });

  const responseHeaders = new Headers();
  for (const headerName of ["content-type", "content-disposition"]) {
    const value = upstream.headers.get(headerName);
    if (value) {
      responseHeaders.set(headerName, value);
    }
  }
  return new NextResponse(upstream.body, {
    headers: responseHeaders,
    status: upstream.status
  });
}

export async function GET(request: NextRequest, context: RouteContext) {
  return proxyToBff(request, context);
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxyToBff(request, context);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  return proxyToBff(request, context);
}
