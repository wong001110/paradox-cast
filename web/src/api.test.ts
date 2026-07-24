import { describe, expect, it } from "vitest";
import { timelineFromSimulation } from "./api";

describe("timelineFromSimulation", () => {
  it("keeps authoritative simulation event order while making it presentable", () => {
    const timeline = timelineFromSimulation([{ type: "movement_arrived", at: 8, details: { character_id: "rei" } }], "run");
    expect(timeline[0]).toMatchObject({ time: "19:18", kind: "movement", detail: "rei" });
  });
});
