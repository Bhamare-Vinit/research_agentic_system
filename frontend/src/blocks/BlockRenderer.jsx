import FindingsBlock from "./FindingsBlock.jsx";
import GapBlock from "./GapBlock.jsx";
import SourcesBlock from "./SourcesBlock.jsx";
import SummaryBlock from "./SummaryBlock.jsx";
import UnknownBlock from "./UnknownBlock.jsx";
import UpdateBlock from "./UpdateBlock.jsx";

const RENDERERS = {
  summary: SummaryBlock,
  findings: FindingsBlock,
  sources: SourcesBlock,
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

export default function BlockRenderer({ blocks }) {
  if (!Array.isArray(blocks) || !blocks.length) {
    return <p className="status">Nothing came back for this turn.</p>;
  }

  return blocks.map((raw, index) => {
    const block = normalise(raw);
    const Renderer = RENDERERS[block.type] || UnknownBlock;

    try {
      return <Renderer key={index} block={block} />;
    } catch {
      return <UnknownBlock key={index} block={block} />;
    }
  });
}
