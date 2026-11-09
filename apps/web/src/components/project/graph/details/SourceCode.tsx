"use client";

import { Highlight } from "prism-react-renderer";
import { sourceTheme } from "./sourceTheme";

interface Props {
  source: string;
  /** 1-indexed line number of the first line of `source`. */
  startLine: number;
  language?: string;
  /** Show the line-number gutter; off for short snippets such as docstring examples. */
  showLineNumbers?: boolean;
  className?: string;
}

/** Read-only, line-numbered, syntax-highlighted code that scrolls sideways instead of wrapping. */
export function SourceCode({ source, startLine, language = "python", showLineNumbers = true, className }: Props) {
  return (
    <Highlight theme={sourceTheme} code={source.replace(/\n$/, "")} language={language}>
      {({ tokens, getLineProps, getTokenProps }) => (
        <pre
          className={`overflow-auto font-mono text-[11px] leading-5 bg-muted/40 [scrollbar-width:thin] [scrollbar-color:var(--border)_transparent] [&::-webkit-scrollbar]:size-1.5 [&::-webkit-scrollbar-corner]:bg-transparent [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-border [&::-webkit-scrollbar-track]:bg-transparent ${className ?? ""}`}
        >
          <code className="block min-w-max py-2">
            {tokens.map((line, i) => (
              <div key={i} {...getLineProps({ line })} className="flex px-0">
                {showLineNumbers && (
                  <span className="w-10 shrink-0 pr-3 text-right text-muted-foreground/70 select-none">
                    {startLine + i}
                  </span>
                )}
                <span className={showLineNumbers ? "whitespace-pre pr-3" : "whitespace-pre px-3"}>
                  {line.map((token, key) => (
                    <span key={key} {...getTokenProps({ token })} />
                  ))}
                </span>
              </div>
            ))}
          </code>
        </pre>
      )}
    </Highlight>
  );
}
