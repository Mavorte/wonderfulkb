import { useMemo } from "react";
import { Outlet, matchPath, useLocation } from "react-router-dom";
import QueueList from "./QueueList";
import triage from "./triage";
import useQueue from "./useQueue";
import type { QueueContext } from "./useQueueContext";

/** The work queue as a list next to the selected case, which opens in the main pane. */
export default function QueueLayout() {
  const state = useQueue();
  const queue = useMemo(() => (state.payload ? triage(state.payload.cases) : undefined), [state.payload]);
  const { pathname } = useLocation();
  const selectedId = matchPath("/cases/:caseId", pathname)?.params.caseId;

  return (
    <div className="bo-split">
      <QueueList state={state} queue={queue} selectedId={selectedId} />
      <div className="bo-split__detail">
        <Outlet context={{ ...state, queue } satisfies QueueContext} />
      </div>
    </div>
  );
}
