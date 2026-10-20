import type { Tier } from "./triage";

const tierTitle: Record<Tier, string> = {
  decision: "Needs your decision",
  waiting: "Waiting on client",
  processing: "Processing",
  done: "Completed",
};

export default tierTitle;
