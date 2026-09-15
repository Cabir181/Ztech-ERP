/** Small presentational building blocks shared by every screen. */

import type { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonVariant = "primary" | "default" | "danger" | "ghost";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: "sm" | "md";
  busy?: boolean;
}

export function Button({ variant = "default", size = "md", busy, children, ...rest }: ButtonProps) {
  const classes = ["btn"];
  if (variant !== "default") classes.push(`btn--${variant}`);
  if (size === "sm") classes.push("btn--sm");
  return (
    <button
      type="button"
      {...rest}
      className={[...classes, rest.className].filter(Boolean).join(" ")}
      disabled={rest.disabled || busy}
      aria-busy={busy || undefined}
    >
      {busy ? <span className="spinner" aria-hidden="true" /> : null}
      {children}
    </button>
  );
}

export type BadgeTone = "neutral" | "success" | "danger" | "warning" | "info";

export function Badge({ tone = "neutral", children }: { tone?: BadgeTone; children: ReactNode }) {
  return <span className={`badge badge--${tone}`}>{children}</span>;
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <>
      <span className="spinner" aria-hidden="true" />
      <span className="visually-hidden">{label}</span>
    </>
  );
}

export function Banner({
  tone = "info",
  title,
  children,
}: {
  tone?: "error" | "warning" | "info" | "success";
  title?: string;
  children?: ReactNode;
}) {
  return (
    // Assertive only for errors: a routine notice should not interrupt a screen
    // reader mid-sentence.
    <div className={`banner banner--${tone}`} role={tone === "error" ? "alert" : "status"}>
      <div className="banner__body">
        {title ? <div className="banner__title">{title}</div> : null}
        {children}
      </div>
    </div>
  );
}

/** Shown while a screen's first load is in flight. */
export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div className="state" role="status" aria-live="polite">
      <Spinner label={label} />
      <span>{label}…</span>
    </div>
  );
}

/** Shown when a list legitimately has nothing in it. */
export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="state">
      <span className="state__title">{title}</span>
      {description ? <span>{description}</span> : null}
      {action}
    </div>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <h1>{title}</h1>
        {description ? <p className="page-header__sub">{description}</p> : null}
      </div>
      {actions ? <div className="page-header__actions">{actions}</div> : null}
    </header>
  );
}

export function Card({
  title,
  hint,
  children,
}: {
  title?: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <section className="card">
      {title ? <h2 className="card__title">{title}</h2> : null}
      {hint ? <p className="card__hint">{hint}</p> : null}
      {children}
    </section>
  );
}

/** Renders a timestamp in the viewer's locale, with the exact value on hover. */
export function DateTime({ value }: { value: string | null }) {
  if (!value) return <span className="text-muted">—</span>;
  const parsed = new Date(value);
  return (
    <time dateTime={value} title={parsed.toISOString()}>
      {parsed.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
    </time>
  );
}
