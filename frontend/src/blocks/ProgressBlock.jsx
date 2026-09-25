const AGENT_LABELS = {
  main: "dossier",
  research: "researcher",
};

export default function ProgressBlock({ status, steps }) {
  return (
    <section className="progress">
      <div className="now">
        <span className="pulse" />
        {status}
      </div>
      {steps.length > 0 && (
        <ol className="steps">
          {steps.map((step, index) => (
            <li key={index}>
              <span className={`who ${step.agent || "main"}`}>
                {AGENT_LABELS[step.agent] || step.agent || "dossier"}
              </span>
              <span className="what">{step.tool}</span>
              <span className="detail">{step.message}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
