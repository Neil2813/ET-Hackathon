import React from "react";

interface MarkdownRendererProps {
  content: string;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content }) => {
  if (!content) return null;

  // Split content by paragraphs or blocks (like tables and lists)
  const blocks = content.split("\n\n");

  const parseLine = (line: string): React.ReactNode[] => {
    // Basic inline formatting: **bold**
    const parts = line.split(/(\*\*[^*]+\*\*)/g);
    return parts.map((part, idx) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={idx} className="font-bold text-foreground">{part.slice(2, -2)}</strong>;
      }
      // Inline `code`
      const codeParts = part.split(/(`[^`]+`)/g);
      if (codeParts.length > 1) {
        return (
          <React.Fragment key={idx}>
            {codeParts.map((subPart, sIdx) => {
              if (subPart.startsWith("`") && subPart.endsWith("`")) {
                return (
                  <code key={sIdx} className="px-1.5 py-0.5 rounded bg-muted font-mono text-xs text-red-400 border border-border">
                    {subPart.slice(1, -1)}
                  </code>
                );
              }
              return subPart;
            })}
          </React.Fragment>
        );
      }
      return part;
    });
  };

  const renderBlock = (block: string, index: number) => {
    const lines = block.split("\n");
    const firstLine = lines[0].trim();

    // 1. Code Block
    if (firstLine.startsWith("```")) {
      const codeLines = lines.slice(1, lines.length - (lines[lines.length - 1].trim() === "```" ? 1 : 0));
      return (
        <pre key={index} className="p-4 my-3 rounded-lg bg-card/60 border border-border font-mono text-xs text-foreground overflow-x-auto shadow-sm max-w-full">
          <code>{codeLines.join("\n")}</code>
        </pre>
      );
    }

    // 2. Heading
    if (firstLine.startsWith("#")) {
      const match = firstLine.match(/^(#{1,6})\s+(.*)$/);
      if (match) {
        const level = match[1].length;
        const text = match[2];
        const headingStyles = {
          1: "text-lg font-headline font-bold text-foreground border-b border-border pb-1 mt-4 mb-2",
          2: "text-md font-headline font-bold text-foreground/90 mt-3 mb-1.5",
          3: "text-sm font-headline font-bold text-foreground/80 mt-2 mb-1.5",
          4: "text-xs font-headline font-bold text-foreground/70",
          5: "text-xs font-bold text-muted-foreground",
          6: "text-[10px] font-bold text-muted-foreground font-mono"
        };
        const className = headingStyles[level as keyof typeof headingStyles] || headingStyles[3];
        return React.createElement(`h${Math.min(level, 6)}`, { key: index, className }, parseLine(text));
      }
    }

    // 3. Table
    if (firstLine.startsWith("|") && lines.some(l => l.includes("|-") || l.includes("|:-") || l.includes("| -"))) {
      const rows = lines.filter(l => l.trim().startsWith("|") && l.trim().endsWith("|"));
      if (rows.length > 1) {
        // Parse rows
        const parsedRows = rows.map(r => r.split("|").map(c => c.trim()).filter((_, i, a) => i > 0 && i < a.length - 1));
        // Identify separator row
        const separatorIdx = parsedRows.findIndex(r => r.every(c => c.startsWith("-") || c.startsWith(":") || c === ""));
        
        let headers: string[] = [];
        let bodyRows: string[][] = [];
        if (separatorIdx !== -1) {
          headers = parsedRows.slice(0, separatorIdx)[0] || [];
          bodyRows = parsedRows.slice(separatorIdx + 1);
        } else {
          bodyRows = parsedRows;
        }

        return (
          <div key={index} className="overflow-x-auto my-3 border border-border rounded-lg shadow-sm">
            <table className="min-w-full divide-y divide-border text-xs bg-card/25 text-left font-sans">
              {headers.length > 0 && (
                <thead className="bg-muted/50 font-headline font-bold text-foreground/80 uppercase tracking-wider text-[10px]">
                  <tr>
                    {headers.map((h, i) => (
                      <th key={i} className="px-4 py-2 border-r border-border last:border-r-0">{h}</th>
                    ))}
                  </tr>
                </thead>
              )}
              <tbody className="divide-y divide-border">
                {bodyRows.map((row, rIdx) => (
                  <tr key={rIdx} className="hover:bg-muted/20 transition-colors">
                    {row.map((cell, cIdx) => (
                      <td key={cIdx} className="px-4 py-2 border-r border-border last:border-r-0 text-muted-foreground font-medium">
                        {parseLine(cell)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      }
    }

    // 4. Bullet List
    if (firstLine.startsWith("- ") || firstLine.startsWith("* ")) {
      return (
        <ul key={index} className="list-disc list-inside pl-4 my-2.5 space-y-1.5 text-xs text-muted-foreground font-medium">
          {lines.map((l, lIdx) => {
            const clean = l.replace(/^[-*]\s+/, "");
            return <li key={lIdx}>{parseLine(clean)}</li>;
          })}
        </ul>
      );
    }

    // 5. Numbered List
    if (/^\d+\.\s+/.test(firstLine)) {
      return (
        <ol key={index} className="list-decimal list-inside pl-4 my-2.5 space-y-1.5 text-xs text-muted-foreground font-medium">
          {lines.map((l, lIdx) => {
            const clean = l.replace(/^\d+\.\s+/, "");
            return <li key={lIdx}>{parseLine(clean)}</li>;
          })}
        </ol>
      );
    }

    // 6. Normal Paragraph
    return (
      <p key={index} className="text-xs leading-relaxed text-muted-foreground font-sans my-2">
        {lines.map((line, lIdx) => (
          <React.Fragment key={lIdx}>
            {lIdx > 0 && <br />}
            {parseLine(line)}
          </React.Fragment>
        ))}
      </p>
    );
  };

  return <div className="space-y-1 font-sans">{blocks.map((block, idx) => renderBlock(block, idx))}</div>;
};
