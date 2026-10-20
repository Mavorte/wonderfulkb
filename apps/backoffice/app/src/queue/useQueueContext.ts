import { useOutletContext } from "react-router-dom";
import type { TriagedCase } from "./triage";
import type { QueueState } from "./useQueue";

export type QueueContext = QueueState & { queue: TriagedCase[] | undefined };

/** The queue context of the page shown next to the queue list. */
export default function useQueueContext() {
  return useOutletContext<QueueContext>();
}
