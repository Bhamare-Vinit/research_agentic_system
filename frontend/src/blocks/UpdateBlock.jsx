function Record({ finding, stale }) {
  return (
    <div className={stale ? "record stale" : "record"}>
      <div className="claim">{finding.claim}</div>
      <div className="record-meta">
        <a href={finding.source} target="_blank" rel="noreferrer">
          {finding.source}
        </a>
        <span>{finding.date}</span>
      </div>
    </div>
  );
}

export default function UpdateBlock({ block }) {
  const byDate = [...block.findings].sort((a, b) =>
    String(a.date || "").localeCompare(String(b.date || ""))
  );
  const latest = byDate.length ? byDate[byDate.length - 1] : null;
  const earlier = byDate.slice(0, -1);

  return (
    <section className="block update">
      <h2>What changed</h2>
      {block.text && <p>{block.text}</p>}
      {byDate.length > 0 && (
        <div className="change">
          <div>
            <h3>Earlier</h3>
            {earlier.length === 0 && <p className="status">nothing earlier on file</p>}
            {earlier.map((finding) => (
              <Record key={finding.id} finding={finding} stale />
            ))}
          </div>
          <div>
            <h3>Now</h3>
            {latest && <Record finding={latest} />}
          </div>
        </div>
      )}
    </section>
  );
}
