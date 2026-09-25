import FindingsBlock from "./FindingsBlock.jsx";
import GapBlock from "./GapBlock.jsx";
import SummaryBlock from "./SummaryBlock.jsx";
import UnknownBlock from "./UnknownBlock.jsx";
import UpdateBlock from "./UpdateBlock.jsx";

const DETAIL_RENDERERS = {
  findings: FindingsBlock,
  gap: GapBlock,
  update: UpdateBlock,
};

function normalise(block) {
  return {
    type: block?.type,
    text: typeof block?.text === "string" ? block.text : null,
    findings: Array.isArray(block?.findings) ? block.findings : [],
  };
}

function uniqueSources(blocks) {
  return new Set(blocks.flatMap((block) => block.findings.map((finding) => finding.source)));
}

function detailLabels(details) {
  const labels = [];
  const records = details
    .filter((block) => block.type === "findings" || block.type === "update")
    .reduce((total, block) => total + block.findings.length, 0);
  const sources = uniqueSources(details).size;

  if (records) labels.push(records === 1 ? "1 finding" : `${records} findings`);
  if (sources) labels.push(sources === 1 ? "1 source" : `${sources} sources`);
  if (details.some((block) => block.type === "update")) labels.push("changed");
  if (details.some((block) => block.type === "gap")) labels.push("gap");
  return labels;
}

export default function BlockRenderer({ blocks, fallbackText, footer }) {
  const normalised = Array.isArray(blocks) ? blocks.map(normalise) : [];
  const summaries = normalised.filter((block) => block.type === "summary" && block.text);
  const details = normalised.filter(
    (block) => block.type !== "summary" && block.type !== "sources"
  );

  const response = summaries.length
    ? summaries.map((block) => block.text).join("\n\n")
    : fallbackText || "Nothing came back for this turn.";

  return (
    <>
      <SummaryBlock text={response} />
      {(details.length > 0 || footer) && (
        <details className="details">
          <summary>
            <span className="details-title">Details</span>
            {detailLabels(details).map((label) => (
              <span key={label} className="chip">
                {label}
              </span>
            ))}
          </summary>
          <div className="details-body">
            {details.map((block, index) => {
              const Renderer = DETAIL_RENDERERS[block.type] || UnknownBlock;
              try {
                return <Renderer key={index} block={block} />;
              } catch {
                return <UnknownBlock key={index} block={block} />;
              }
            })}
            {footer}
          </div>
        </details>
      )}
    </>
  );
}
