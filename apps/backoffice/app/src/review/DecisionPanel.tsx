import { useEffect, useRef, useState } from "react";
import { useWonderful } from "@wonderful/app-sdk";
import getErrorCode from "../getErrorCode";
import type { CaseView } from "./evaluation";
import useCorrectionCall, { describeCall, isActive } from "./useCorrectionCall";

type DecisionKind = "approve" | "return" | "escalate" | "reject";

const options: { kind: DecisionKind; label: string }[] = [
  { kind: "approve", label: "Approve disbursement" },
  { kind: "return", label: "Request correction" },
  { kind: "escalate", label: "Escalate to risk" },
  { kind: "reject", label: "Reject" },
];

const notConnected = "Recording decisions isn't connected yet";

const callErrors: Record<string, string> = {
  no_contact: "The client has no contact person on file to verify.",
  case_not_found: "The case wasn't found.",
  not_configured: "Calling isn't configured for this workspace.",
  call_failed: "The call couldn't be placed. Try again.",
};

type CallState = { status: "idle" | "calling" } | { status: "failed"; message: string };

export default function DecisionPanel({ view }: { view: CaseView }) {
  const recommended = view.decision;
  const [choice, setChoice] = useState<DecisionKind | null>(recommended);
  const [reason, setReason] = useState("");
  const [showError, setShowError] = useState(false);
  const [noteOpen, setNoteOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [call, setCall] = useState<CallState>({ status: "idle" });
  const { api } = useWonderful();
  const { call: lastCall, refresh } = useCorrectionCall(view.evaluation.case_id);
  const outcome = lastCall && describeCall(lastCall);
  const dialogRef = useRef<HTMLDivElement>(null);

  const deviates = recommended !== null && choice !== recommended;

  useEffect(() => {
    if (!confirming) return;
    dialogRef.current?.querySelector<HTMLElement>(".kb-btn--primary")?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setConfirming(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [confirming]);

  const confirm = () => {
    if (deviates && !reason.trim()) return setShowError(true);
    if (choice === "return") setConfirming(true);
  };

  const placeCall = async () => {
    setCall({ status: "calling" });
    try {
      await api.invokeFunction("backoffice/correction-call", {
        method: "POST",
        params: {
          case_id: view.evaluation.case_id,
          findings: view.fixes.map((f) => ({ label: f.label, found: f.found })),
          note: reason.trim(),
        },
      });
      setCall({ status: "idle" });
      setConfirming(false);
      refresh();
    } catch (error) {
      const code = getErrorCode(error);
      setCall({ status: "failed", message: callErrors[code ?? ""] ?? callErrors.call_failed });
    }
  };

  return (
    <>
      <fieldset className="cr-options">
        <legend>Your decision</legend>
        {options.map((o) => (
          <label key={o.kind} className={`cr-option${choice === o.kind ? " is-selected" : ""}`}>
            <input
              type="radio"
              name="cr-decision"
              value={o.kind}
              checked={choice === o.kind}
              onChange={() => {
                setChoice(o.kind);
                setShowError(false);
              }}
            />
            <span className="cr-option__text">
              <span className="cr-option__label">
                {o.label}
                {o.kind === recommended && <span className="cr-option__tag">Recommended</span>}
              </span>
            </span>
          </label>
        ))}
      </fieldset>
      {deviates || noteOpen ? (
      <div className="kb-field">
        <label htmlFor="cr-reason">{deviates ? "Reason (required)" : "Note"}</label>
        <textarea
          id="cr-reason"
          className="kb-input cr-note"
          rows={2}
          value={reason}
          aria-invalid={showError || undefined}
          onChange={(e) => {
            setReason(e.target.value);
            setShowError(false);
          }}
        />
        {showError && <span className="kb-field__error">Explain why you differ from the recommendation.</span>}
      </div>
      ) : (
        <button type="button" className="kb-link cr-add-note" onClick={() => setNoteOpen(true)}>
          + Add note
        </button>
      )}
      {choice === "return" ? (
        <>
          <button
            type="button"
            className="kb-btn kb-btn--primary cr-confirm"
            onClick={confirm}
            disabled={isActive(lastCall) || view.fixes.length === 0}
          >
            Request correction
          </button>
          {outcome ? (
            <p className={`cr-call-status cr-call-status--${outcome.tone}`} role="status">
              {outcome.text}
            </p>
          ) : (
            view.fixes.length === 0 && <p className="cr-disabled-note">There are no findings to correct.</p>
          )}
        </>
      ) : (
        <>
          <button type="button" className="kb-btn kb-btn--primary cr-confirm" disabled title={choice ? notConnected : undefined}>
            Confirm decision
          </button>
          <p className="cr-disabled-note">{choice ? notConnected : "Choose a decision"}</p>
        </>
      )}

      {confirming && (
        <div className="cr-overlay" onClick={(e) => e.target === e.currentTarget && setConfirming(false)}>
          <div className="cr-dialog" role="dialog" aria-modal="true" aria-labelledby="cr-dialog-title" ref={dialogRef}>
            <header className="cr-dialog__head">
              <div>
                <p className="cr-eyebrow">Outbound call to the client</p>
                <h2 className="cr-dialog__title" id="cr-dialog-title">
                  Request correction
                </h2>
              </div>
              <button type="button" className="cr-dialog__close" aria-label="Close" onClick={() => setConfirming(false)}>
                <svg className="kb-icon" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="m12 10.6 5-5 1.4 1.4-5 5 5 5-1.4 1.4-5-5-5 5L5.6 17l5-5-5-5L7 5.6l5 5Z" />
                </svg>
              </button>
            </header>
            <div className="cr-dialog__body">
              <p className="cr-dialog__lead">
                An AI agent calls {view.borrower ?? "the client"}, verifies the contact's surname, summarises the problem and emails the full list
                with an upload link.
              </p>
              <ol className="cr-dialog__list">
                {view.fixes.map((f) => (
                  <li key={f.ruleId}>
                    <strong>{f.label}</strong>
                    {f.found && <span>: {f.found}</span>}
                  </li>
                ))}
              </ol>
              {reason.trim() && (
                <p className="cr-dialog__lead">
                  <strong>Your note:</strong> {reason.trim()}
                </p>
              )}
              {call.status === "failed" && (
                <p className="kb-field__error" role="alert">
                  {call.message}
                </p>
              )}
            </div>
            <footer className="cr-dialog__foot">
              <button type="button" className="kb-btn kb-btn--secondary" onClick={() => setConfirming(false)}>
                Back
              </button>
              <button type="button" className="kb-btn kb-btn--primary" onClick={placeCall} disabled={call.status === "calling"}>
                {call.status === "calling" ? "Calling…" : "Call client"}
              </button>
            </footer>
          </div>
        </div>
      )}
    </>
  );
}
