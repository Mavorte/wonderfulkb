import { useEffect, useRef, useState } from "react";
import type { CaseView } from "./evaluation";

type DecisionKind = "approve" | "return" | "escalate" | "reject";

const options: { kind: DecisionKind; label: string }[] = [
  { kind: "approve", label: "Approve disbursement" },
  { kind: "return", label: "Return for corrections" },
  { kind: "escalate", label: "Escalate to risk" },
  { kind: "reject", label: "Reject" },
];

const notConnected = "Recording decisions isn't connected yet";

function draftFor(view: CaseView) {
  const { evaluation, fixes, borrower } = view;
  const steps = fixes.map((f, i) => `${i + 1}. ${f.label}: ${f.found ?? "needs review"}`).join("\n");
  return {
    to: "",
    subject: `Case ${evaluation.case_id}${borrower ? ` – ${borrower}` : ""}: corrections needed before disbursement`,
    body: `Hello,

the review of case ${evaluation.case_id}${borrower ? ` (${borrower})` : ""} found issues that block disbursement. Please arrange the following with the client:

${steps}

The case will be re-checked once the corrected documents are uploaded.

Thank you,
Back office`,
  };
}

export default function DecisionPanel({ view }: { view: CaseView }) {
  const recommended = view.decision;
  const [choice, setChoice] = useState<DecisionKind>(recommended ?? "escalate");
  const [reason, setReason] = useState("");
  const [showError, setShowError] = useState(false);
  const [noteOpen, setNoteOpen] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const [draft, setDraft] = useState(() => draftFor(view));
  const [copied, setCopied] = useState<"idle" | "done" | "failed">("idle");
  const dialogRef = useRef<HTMLDivElement>(null);

  const deviates = recommended !== null && choice !== recommended;

  useEffect(() => {
    if (!drafting) return;
    dialogRef.current?.querySelector<HTMLElement>("textarea")?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setDrafting(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drafting]);

  const confirm = () => {
    if (deviates && !reason.trim()) return setShowError(true);
    if (choice === "return") setDrafting(true);
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(`${draft.subject}\n\n${draft.body}`);
      setCopied("done");
    } catch {
      setCopied("failed");
    }
    window.setTimeout(() => setCopied("idle"), 2000);
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
        <button type="button" className="kb-btn kb-btn--primary cr-confirm" onClick={confirm}>
          Review request to sales
        </button>
      ) : (
        <>
          <button type="button" className="kb-btn kb-btn--primary cr-confirm" disabled title={notConnected}>
            Confirm decision
          </button>
          <p className="cr-disabled-note">{notConnected}</p>
        </>
      )}

      {drafting && (
        <div className="cr-overlay" onClick={(e) => e.target === e.currentTarget && setDrafting(false)}>
          <div className="cr-dialog" role="dialog" aria-modal="true" aria-labelledby="cr-dialog-title" ref={dialogRef}>
            <header className="cr-dialog__head">
              <div>
                <p className="cr-eyebrow">Drafted from the evaluation · sending isn't connected yet</p>
                <h2 className="cr-dialog__title" id="cr-dialog-title">
                  Request to sales
                </h2>
              </div>
              <button type="button" className="cr-dialog__close" aria-label="Close" onClick={() => setDrafting(false)}>
                <svg className="kb-icon" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="m12 10.6 5-5 1.4 1.4-5 5 5 5-1.4 1.4-5-5-5 5L5.6 17l5-5-5-5L7 5.6l5 5Z" />
                </svg>
              </button>
            </header>
            <div className="cr-dialog__body">
              <div className="kb-field">
                <label htmlFor="cr-to">To</label>
                <input id="cr-to" className="kb-input" placeholder="Sales owner of the case" value={draft.to} onChange={(e) => setDraft({ ...draft, to: e.target.value })} />
              </div>
              <div className="kb-field">
                <label htmlFor="cr-subject">Subject</label>
                <input
                  id="cr-subject"
                  className="kb-input"
                  value={draft.subject}
                  onChange={(e) => setDraft({ ...draft, subject: e.target.value })}
                />
              </div>
              <div className="kb-field">
                <label htmlFor="cr-body">Message</label>
                <textarea
                  id="cr-body"
                  className="kb-input cr-dialog__text"
                  rows={16}
                  value={draft.body}
                  onChange={(e) => setDraft({ ...draft, body: e.target.value })}
                />
              </div>
            </div>
            <footer className="cr-dialog__foot">
              <button type="button" className="kb-btn kb-btn--secondary" onClick={() => setDrafting(false)}>
                Back
              </button>
              <button type="button" className="kb-btn kb-btn--tertiary" onClick={copy}>
                {copied === "done" ? "Copied" : copied === "failed" ? "Copy blocked — select the text" : "Copy message"}
              </button>
              <button type="button" className="kb-btn kb-btn--primary" disabled title="Sending isn't connected yet">
                Send and return case
              </button>
            </footer>
          </div>
        </div>
      )}
    </>
  );
}
