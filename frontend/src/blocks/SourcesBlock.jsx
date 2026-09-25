function hostOf(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export default function SourcesBlock({ block }) {
  const urls = [...new Set(block.findings.map((finding) => finding.source))];
  if (!urls.length) return null;

  return (
    <section className="block">
      <h2>Sources</h2>
      <ul className="sources">
        {urls.map((url) => (
          <li key={url}>
            <a href={url} target="_blank" rel="noreferrer">
              <span className="host">{hostOf(url)}</span>
              <span className="url">{url}</span>
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}
