async function fields(request) {
  const ctype = request.headers.get("content-type") || "";
  if (ctype.includes("json")) {
    const j = await request.json().catch(() => ({}));
    return { title: String(j.title || ""), body: String(j.body || "") };
  }
  const fd = await request.formData();
  return { title: String(fd.get("title") || ""), body: String(fd.get("body") || "") };
}

export async function POST(request) {
  const hook = process.env.SUGGEST_WEBHOOK_URL;
  if (!hook) return new Response("suggestions disabled", { status: 503 });
  const raw = await fields(request);
  const title = raw.title.trim().slice(0, 256);
  const body = raw.body.trim().slice(0, 4096);
  if (!body) return new Response("body required", { status: 400 });
  const embed = { description: body };
  if (title) embed.title = title;
  const r = await fetch(hook, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ embeds: [embed] }),
  });
  if (!r.ok) return new Response("failed", { status: 502 });
  if ((request.headers.get("content-type") || "").includes("json")) {
    return Response.json({ ok: true });
  }
  return Response.redirect(new URL("/suggest?ok=1", request.url), 303);
}
