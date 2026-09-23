export default function UnknownBlock({ block }) {
  return (
    <section className="block unknown">
      <h2>{block.type || "untyped"} block</h2>
      {block.text && <p>{block.text}</p>}
      {!block.text && <pre>{JSON.stringify(block, null, 2)}</pre>}
    </section>
  );
}
