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
              {url}
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}
