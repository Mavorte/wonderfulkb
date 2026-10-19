import { useId, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { filterClients } from "./filterClients";
import type { Client } from "./mockClients";

type Props = {
  clients: Client[];
  value: Client | null;
  onChange: (client: Client | null) => void;
  error?: string;
  disabled?: boolean;
};

export function ClientCombobox({ clients, value, onChange, error, disabled }: Props) {
  const id = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);

  const results = useMemo(() => filterClients(clients, query), [clients, query]);
  const listId = `${id}-list`;
  const errorId = `${id}-error`;
  const optionId = (i: number) => `${id}-opt-${i}`;

  const select = (client: Client) => {
    onChange(client);
    setQuery("");
    setOpen(false);
  };

  const clear = () => {
    onChange(null);
    setQuery("");
    setOpen(true);
    inputRef.current?.focus();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!open) return setOpen(true);
      const step = e.key === "ArrowDown" ? 1 : -1;
      setActive((i) => (i + step + results.length) % Math.max(results.length, 1));
    } else if (e.key === "Enter" && open && results[active]) {
      e.preventDefault();
      select(results[active]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div className="kb-field">
      <label htmlFor={id}>Client</label>
      <div className="bo-combobox">
        <svg className="kb-icon kb-icon--muted bo-combobox__search" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M10.5 4a6.5 6.5 0 0 1 5.2 10.4l4.45 4.44-1.41 1.42-4.45-4.45A6.5 6.5 0 1 1 10.5 4Zm0 2a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9Z" />
        </svg>
        <input
          ref={inputRef}
          id={id}
          className="kb-input bo-combobox__input"
          type="text"
          role="combobox"
          autoComplete="off"
          placeholder={value ? undefined : "Search by name or client ID"}
          value={open || !value ? query : `${value.name} · ${value.id}`}
          disabled={disabled}
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={open && results[active] ? optionId(active) : undefined}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          onChange={(e) => {
            setQuery(e.target.value);
            setActive(0);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onClick={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={onKeyDown}
        />
        {value && !disabled && (
          <button type="button" className="bo-combobox__clear" aria-label="Clear client" onClick={clear}>
            <svg className="kb-icon" viewBox="0 0 24 24" aria-hidden="true">
              <path d="m12 10.59 4.95-4.95 1.41 1.41L13.41 12l4.95 4.95-1.41 1.41L12 13.41l-4.95 4.95-1.41-1.41L10.59 12 5.64 7.05l1.41-1.41L12 10.59Z" />
            </svg>
          </button>
        )}
        {open && (
          <ul id={listId} role="listbox" aria-label="Clients" className="bo-combobox__list">
            {results.length === 0 ? (
              <li className="bo-combobox__empty">No client matches “{query}”</li>
            ) : (
              results.map((c, i) => (
                <li
                  key={c.id}
                  id={optionId(i)}
                  role="option"
                  aria-selected={value?.id === c.id}
                  className={`bo-combobox__option${i === active ? " is-active" : ""}`}
                  onMouseDown={(e) => e.preventDefault()}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => select(c)}
                >
                  <span className="bo-combobox__name">{c.name}</span>
                  <span className="bo-combobox__meta">
                    {c.id} · born {new Date(c.birthDate).toLocaleDateString("cs-CZ")}
                  </span>
                </li>
              ))
            )}
          </ul>
        )}
      </div>
      {error && (
        <p id={errorId} className="kb-field__error bo-field-error">
          {error}
        </p>
      )}
    </div>
  );
}
