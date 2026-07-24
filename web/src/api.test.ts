import { describe, expect, it } from "vitest";
import { timelineFromSimulation } from "./api";

describe("timelineFromSimulation", () => {
  it("keeps authoritative simulation order and replay metadata", () => {
    const timeline = timelineFromSimulation([
      {
        type: "observation",
        at: 8,
        details: {
          character_id: "hana",
          location_id: "lounge",
          content: "A torn ticket says yesterday.",
          source: "direct_observation",
        },
      },
    ], "run");

    expect(timeline[0]).toMatchObject({
      time: "19:18",
      kind: "observation",
      characterId: "hana",
      locationId: "lounge",
      content: "A torn ticket says yesterday.",
      source: "direct_observation",
    });
  });

  it("rolls replay timestamps across the hour boundary", () => {
    const timeline = timelineFromSimulation([
      { type: "movement_arrived", at: 55, details: { character_id: "rei", location_id: "station" } },
    ], "run");

    expect(timeline[0]).toMatchObject({ time: "20:05", title: "Rei arrives" });
  });

  it("prepends an explainable external intervention to a branch replay", () => {
    const timeline = timelineFromSimulation(
      [{ type: "wait", at: 2, details: { character_id: "mira", location_id: "cafe" } }],
      "branch",
      [{ kind: "delay_information", reason: "The courier arrives six minutes late.", details: { action_id: "hana-ticket" } }],
    );

    expect(timeline[0]).toMatchObject({
      kind: "intervention",
      title: "External intervention: Delay Information",
      content: "The courier arrives six minutes late.",
      source: "external_intervention",
    });
    expect(timeline[1]).toMatchObject({ characterId: "mira", locationId: "cafe" });
  });
});
