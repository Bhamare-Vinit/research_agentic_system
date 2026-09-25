export default function FindingsBlock({ block }) {
  if (!block.findings.length) return null;

  return (
    <section className="block">
      <h2>Findings</h2>
      {block.text && <p>{block.text}</p>}
      <ul className="records">
        {block.findings.map((finding) => (
          <li key={finding.id} className={finding.active === false ? "record stale" : "record"}>
            <div className="claim">{finding.claim}</div>
            <div className="record-meta">
              <a href={finding.source} target="_blank" rel="noreferrer">
                {finding.source}
              </a>
              <span>{finding.date}</span>
              {finding.active === false && <span className="tag">superseded</span>}
              <span className="tag id">{finding.id}</span>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
