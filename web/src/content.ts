export type TimelineEvent = {
  id: string;
  time: string;
  kind: "movement" | "observation" | "dialogue" | "intervention";
  title: string;
  detail: string;
};

export type CastMember = {
  id: string;
  name: string;
  role: string;
  age: number;
  archetype: string;
  color: string;
  runtime: string;
};

export const productCopy = {
  title: "Paradox Cast",
  tagline: "Every choice leaves a mark. Every timeline hides a truth.",
  foundation: "Build a scenario, cast adult characters, lock a run manifest, and observe explainable timeline divergence.",
  caseTitle: "The Vanishing of April 14th",
} as const;

export const defaultCast: CastMember[] = [
  { id: "hana", name: "Hana", role: "The Empath", age: 23, archetype: "Warm observer", color: "#c18b7e", runtime: "Host-funded / Mock" },
  { id: "rei", name: "Rei", role: "The Analyst", age: 25, archetype: "Careful reasoner", color: "#637599", runtime: "Host-funded / Mock" },
  { id: "mira", name: "Mira", role: "The Trickster", age: 21, archetype: "Playful disruptor", color: "#a47eb3", runtime: "Bring-your-own / Mock" },
  { id: "kagura", name: "Kagura", role: "The Observer", age: 26, archetype: "Quiet witness", color: "#627060", runtime: "Host-funded / Mock" },
];

export const originalTimeline: TimelineEvent[] = [
  { id: "e1", time: "19:10", kind: "movement", title: "Rei leaves the lounge", detail: "Route: Safehouse Lounge → Old Station · 8 min" },
  { id: "e2", time: "19:14", kind: "observation", title: "Hana notices a torn ticket", detail: "Source: café table · confidence: medium" },
  { id: "e3", time: "19:18", kind: "dialogue", title: "Mira overhears half a call", detail: "Partial observation near the east corridor" },
  { id: "e4", time: "19:22", kind: "dialogue", title: "Rei: “The date cannot be yesterday.”", detail: "Conversation at Old Station" },
];

export const branchedTimeline: TimelineEvent[] = [
  { id: "b1", time: "19:10", kind: "intervention", title: "Evidence is revealed to Hana", detail: "External intervention · ticket is delivered at the lounge" },
  { id: "b2", time: "19:12", kind: "movement", title: "Hana redirects Rei", detail: "Route changes to Café Nocturne · 5 min" },
  { id: "b3", time: "19:16", kind: "observation", title: "Rei and Mira cross paths", detail: "Encounter resolved by the simulation kernel" },
  { id: "b4", time: "19:20", kind: "dialogue", title: "Mira shares the call fragment", detail: "New information source: Mira · confidence: medium" },
];

export const adminSummary = [
  ["Active lobbies", "3", "Two public · one unlisted"],
  ["Running timelines", "1", "Manifest PXC-APR14-001"],
  ["Public content", "12", "8 cards · 4 scenarios"],
  ["Mock runtime calls", "18", "No provider credential exposed"],
] as const;

export const differenceSummary = [
  "Evidence reached Hana 12 minutes earlier.",
  "Rei and Mira had one simulation-resolved encounter.",
  "No player memory was edited; beliefs changed through observed events.",
];
