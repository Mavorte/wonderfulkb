import { Navigate } from "react-router-dom";
import getCasePath from "../cases/getCasePath";
import useQueueContext from "./useQueueContext";

/** The work queue has no page of its own: it opens the most acute case as soon as the queue loads. */
export default function QueuePage() {
  const { queue } = useQueueContext();
  if (!queue) return null;
  if (queue.length === 0) return <p className="cr-state">The queue is empty.</p>;
  return <Navigate to={getCasePath(queue[0].case_id)} replace />;
}
