export default function SummaryBlock({ block }) {
  return (
    <section className="block">
      <h2>Summary</h2>
      <p>{block.text}</p>
    </section>
  );
}
