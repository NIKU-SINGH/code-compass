import { useMemo, type ReactNode } from "react";
import { parseDocstring, type DocSection } from "./parseDocstring";
import { SourceCode } from "./SourceCode";

/** Text with `code` and ``code`` spans set in the code style. */
function Inline({ text }: { text: string }) {
  const parts = text.split(/(``[^`]+``|`[^`]+`)/g);
  return (
    <>
      {parts.map((part, i) =>
        part.startsWith("`") ? (
          <code key={i} className="rounded bg-muted/60 px-1 py-0.5 font-mono text-[11px] text-foreground">
            {part.replace(/^`+|`+$/g, "")}
          </code>
        ) : (
          part
        )
      )}
    </>
  );
}

function SubHeading({ children }: { children: ReactNode }) {
  return <h4 className="text-[11px] font-medium text-muted-foreground">{children}</h4>;
}

function Section({ section }: { section: DocSection }) {
  return (
    <div className="flex flex-col gap-1.5">
      <SubHeading>{section.title}</SubHeading>
      {section.kind === "entries" && (
        <dl className="flex flex-col gap-2.5 border-l border-border pl-3">
          {section.entries.map((e) => (
            <div key={e.name}>
              <dt className="flex items-baseline gap-2">
                <code className="rounded bg-muted/60 px-1.5 py-0.5 font-mono text-[11px] text-foreground">{e.name}</code>
                {e.type && <span className="font-mono text-[10px] text-muted-foreground">{e.type}</span>}
              </dt>
              {e.text && (
                <dd className="mt-1 leading-relaxed text-foreground/75">
                  <Inline text={e.text} />
                </dd>
              )}
            </div>
          ))}
        </dl>
      )}
      {section.kind === "text" &&
        section.paragraphs.map((p, i) => (
          <p key={i} className="whitespace-pre-line leading-relaxed text-foreground/75">
            <Inline text={p} />
          </p>
        ))}
      {section.kind === "code" && (
        <SourceCode source={section.code} startLine={1} showLineNumbers={false} className="max-h-64 rounded" />
      )}
    </div>
  );
}

/** A docstring laid out as a summary, paragraphs and labelled sections. */
export function Docstring({ text }: { text: string }) {
  const doc = useMemo(() => parseDocstring(text), [text]);
  return (
    <div className="flex flex-col gap-3">
      {doc.summary && (
        <p className="text-[13px] font-medium leading-snug text-foreground">
          <Inline text={doc.summary} />
        </p>
      )}
      {doc.body.map((p, i) => (
        <p key={i} className="whitespace-pre-line leading-relaxed text-foreground/75">
          <Inline text={p} />
        </p>
      ))}
      {doc.sections.map((s) => (
        <Section key={s.title} section={s} />
      ))}
    </div>
  );
}
