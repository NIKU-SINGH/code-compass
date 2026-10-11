type EndRef = string | { id: string };

const idOf = (end: EndRef) => (typeof end === "string" ? end : end.id);

/** An edge end is a bare id before 3d-force-graph runs, and the node object afterwards. */
export interface LinkEnds {
  source: EndRef;
  target: EndRef;
}

/** The focused node plus every node directly connected to it. */
export function neighbourhoodOf(focusId: string, links: ReadonlyArray<LinkEnds>): Set<string> {
  const ids = new Set([focusId]);
  for (const l of links) {
    const s = idOf(l.source);
    const t = idOf(l.target);
    if (s === focusId) ids.add(t);
    else if (t === focusId) ids.add(s);
  }
  return ids;
}

/** True when the link touches the focused node. */
export function linkTouches(focusId: string, link: LinkEnds): boolean {
  return idOf(link.source) === focusId || idOf(link.target) === focusId;
}
