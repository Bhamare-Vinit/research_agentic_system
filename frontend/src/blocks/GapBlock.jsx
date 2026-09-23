export default function GapBlock({ block }) {
  return (
    <section className="block gap">
      <h2>Not in the dossier</h2>
      <p>{block.text}</p>
    </section>
  );
}
