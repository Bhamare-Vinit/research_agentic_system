const AGENT_LABELS = {
  main: "dossier",
  research: "researcher",
};

export default function ProgressBlock({ status, steps }) {
  return (
    <section className="block progress">
      <h2>Still working</h2>
      <p className="now">{status}</p>
      {steps.length > 0 && (
        <ol className="steps">
          {steps.map((step, index) => (
            <li key={index}>
              <span className="who">{AGENT_LABELS[step.agent] || step.agent || "dossier"}</span>
              <span className="what">{step.tool}</span>
              <span className="detail">{step.message}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
