import { describe, expect, it } from "vitest";
import { linkTouches, neighbourhoodOf } from "@/components/project/graph/focusNeighbourhood";

const links = [
  { source: "a", target: "b" },
  { source: { id: "c" }, target: { id: "a" } },
  { source: "d", target: "e" },
];

describe("neighbourhoodOf", () => {
  it("includes the focus and both directions of its edges, for ids and node objects", () => {
    expect([...neighbourhoodOf("a", links)].sort()).toEqual(["a", "b", "c"]);
  });

  it("is just the focus when it has no edges", () => {
    expect([...neighbourhoodOf("z", links)]).toEqual(["z"]);
  });
});

describe("linkTouches", () => {
  it("is true only for links with the focus at an end", () => {
    expect(links.map((l) => linkTouches("a", l))).toEqual([true, true, false]);
  });
});
