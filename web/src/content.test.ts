import { describe, expect, it } from "vitest";
import { branchedTimeline, defaultCast, differenceSummary, productCopy } from "./content";

describe("product shell copy", () => {
  it("keeps the official product name and explainable divergence promise", () => {
    expect(productCopy.title).toBe("Paradox Cast");
    expect(productCopy.foundation).toContain("explainable timeline divergence");
  });

  it("keeps the official cast explicitly adult and offers a legal external branch", () => {
    expect(defaultCast).toHaveLength(4);
    expect(defaultCast.every((character) => character.age >= 18)).toBe(true);
    expect(branchedTimeline[0]?.kind).toBe("intervention");
    expect(differenceSummary.join(" ")).toContain("No player memory was edited");
  });
});
