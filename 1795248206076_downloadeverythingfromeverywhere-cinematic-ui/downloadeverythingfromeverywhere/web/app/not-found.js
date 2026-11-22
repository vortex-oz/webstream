import QueueMark from "./QueueMark.js";

export default function NotFound() {
  return (
    <div id="wrap">
      <header id="header">
        <p className="brand">
          <a href="/">ZYRON</a>
          {" • "}
          <a href="/suggest">suggest</a>
        </p>
        <QueueMark />
      </header>
      <p>not found</p>
    </div>
  );
}
