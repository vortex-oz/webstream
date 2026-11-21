import QueueMark from "../QueueMark.js";

export const metadata = { title: "suggest", robots: { index: false, follow: true } };

export default async function Page({ searchParams }) {
  const ok = String((await searchParams)?.ok || "") === "1";
  const enabled = Boolean(process.env.SUGGEST_WEBHOOK_URL);
  return (
    <div id="wrap">
      <header id="header">
        <h1>
          <a href="/">downloadeverythingfromeverywhere</a>
          {" • "}
          <a href="/suggest">suggest</a>
        </h1>
        <a href="/guide" className="site-guide-link">
          site guide
        </a>
        <QueueMark />
      </header>
      {enabled ? (
        <form action="/api/suggest" method="post">
          <p>
            <input name="title" placeholder="title" autoComplete="off" />
          </p>
          <p>
            <textarea name="body" required placeholder="suggestion or issue" rows={8} />
          </p>
          <p>
            <button type="submit">submit</button>
          </p>
        </form>
      ) : (
        <p>suggestions are disabled on this instance.</p>
      )}
      {enabled && ok ? <p>sent</p> : null}
    </div>
  );
}
