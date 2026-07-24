import { describe, expect, it } from "vitest";
import { productCopy } from "./content";

describe("product shell copy", () => {
  it("keeps the official product name and explainable divergence promise", () => {
    expect(productCopy.title).toBe("Paradox Cast");
    expect(productCopy.foundation).toContain("explainable timeline divergence");
  });
});
