import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";

async function proxy(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const target = `${BACKEND}/api/${path.join("/")}/`;

  // Preserve query string
  const qs = req.nextUrl.search;
  const url = `${target}${qs}`;

  // Forward relevant headers
  const headers = new Headers();
  for (const key of [
    "content-type",
    "x-client-type",
    "cookie",
    "user-agent",
    "authorization",
  ]) {
    const val = req.headers.get(key);
    if (val) headers.set(key, val);
  }

  const body =
    req.method !== "GET" && req.method !== "HEAD"
      ? await req.arrayBuffer()
      : undefined;

  const backendRes = await fetch(url, {
    method: req.method,
    headers,
    body,
    redirect: "manual",
  });

  // Build response
  const resBody = await backendRes.arrayBuffer();
  const response = new NextResponse(resBody, { status: backendRes.status });

  // Forward content-type
  const ct = backendRes.headers.get("content-type");
  if (ct) response.headers.set("Content-Type", ct);

  // Forward Set-Cookie headers (auth tokens)
  for (const cookie of backendRes.headers.getSetCookie()) {
    response.headers.append("Set-Cookie", cookie);
  }

  return response;
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
