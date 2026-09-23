export default function UpdateBlock({ block }) {
  const replaced = block.findings.filter((finding) => !finding.active);
  const current = block.findings.filter((finding) => finding.active);

  return (
    <section className="block update">
      <h2>What changed</h2>
      {block.text && <p>{block.text}</p>}
      <div className="change">
        <div>
          <h3>Previously</h3>
          {replaced.map((finding) => (
            <div key={finding.id} className="record stale">
              <div className="claim">{finding.claim}</div>
              <div className="record-meta">
                <a href={finding.source} target="_blank" rel="noreferrer">
                  {finding.source}
                </a>
                <span>{finding.date}</span>
              </div>
            </div>
          ))}
        </div>
        <div>
          <h3>Now</h3>
          {current.map((finding) => (
            <div key={finding.id} className="record">
              <div className="claim">{finding.claim}</div>
              <div className="record-meta">
                <a href={finding.source} target="_blank" rel="noreferrer">
                  {finding.source}
                </a>
                <span>{finding.date}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
