/** Finds the node a `?focus=` value refers to: a public id, or a bare file path. */
export function findFocusedNode<T extends { public_id: string }>(
  nodes: ReadonlyArray<T>,
  focus: string | null | undefined,
): T | null {
  const wanted = focus?.trim();
  if (!wanted) return null;
  return (
    nodes.find((n) => n.public_id === wanted) ??
    nodes.find((n) => n.public_id === `file::${wanted}`) ??
    null
  );
}
