/**
 * Form primitives.
 *
 * Every control is labelled, describes its own error through
 * `aria-describedby`, and marks itself invalid, so the form is usable with a
 * keyboard and a screen reader rather than by sighted mouse users only.
 */

import { useId } from "react";
import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

interface FieldShellProps {
  label: string;
  required?: boolean;
  hint?: string;
  errors?: string[];
  children: (ids: { id: string; describedBy: string | undefined; invalid: boolean }) => ReactNode;
}

export function Field({ label, required, hint, errors, children }: FieldShellProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const hasErrors = Boolean(errors && errors.length);
  const describedBy = [hint ? hintId : null, hasErrors ? errorId : null].filter(Boolean).join(" ") || undefined;

  return (
    <div className="field">
      {/* The required marker sits outside the <label> on purpose. Inside it, it
          becomes part of the control's accessible name ("Password*"), which
          reads badly to a screen reader and makes the field hard to address in
          tests. The input's own `required` attribute is what carries the
          meaning; this asterisk is decoration. */}
      <span className="field__label-row">
        <label className="field__label" htmlFor={id}>
          {label}
        </label>
        {required ? (
          <span className="field__required" aria-hidden="true">
            *
          </span>
        ) : null}
      </span>
      {children({ id, describedBy, invalid: hasErrors })}
      {hint ? (
        <span className="field__hint" id={hintId}>
          {hint}
        </span>
      ) : null}
      {hasErrors ? (
        <span className="field__error" id={errorId} role="alert">
          {errors!.join(" ")}
        </span>
      ) : null}
    </div>
  );
}

type TextFieldProps = {
  label: string;
  hint?: string;
  errors?: string[];
} & InputHTMLAttributes<HTMLInputElement>;

export function TextField({ label, hint, errors, required, ...input }: TextFieldProps) {
  return (
    <Field label={label} hint={hint} errors={errors} required={required}>
      {({ id, describedBy, invalid }) => (
        <input
          {...input}
          id={id}
          required={required}
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
          className={`control${invalid ? " control--invalid" : ""}`}
        />
      )}
    </Field>
  );
}

type TextAreaFieldProps = {
  label: string;
  hint?: string;
  errors?: string[];
} & TextareaHTMLAttributes<HTMLTextAreaElement>;

export function TextAreaField({ label, hint, errors, required, ...input }: TextAreaFieldProps) {
  return (
    <Field label={label} hint={hint} errors={errors} required={required}>
      {({ id, describedBy, invalid }) => (
        <textarea
          {...input}
          id={id}
          required={required}
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
          className={`control${invalid ? " control--invalid" : ""}`}
        />
      )}
    </Field>
  );
}

type SelectFieldProps = {
  label: string;
  hint?: string;
  errors?: string[];
  options: { value: string; label: string }[];
} & SelectHTMLAttributes<HTMLSelectElement>;

export function SelectField({ label, hint, errors, options, required, ...input }: SelectFieldProps) {
  return (
    <Field label={label} hint={hint} errors={errors} required={required}>
      {({ id, describedBy, invalid }) => (
        <select
          {...input}
          id={id}
          required={required}
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
          className={`control${invalid ? " control--invalid" : ""}`}
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      )}
    </Field>
  );
}

export function CheckboxField({
  label,
  hint,
  checked,
  onChange,
  disabled,
}: {
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
}) {
  const id = useId();
  const hintId = `${id}-hint`;
  return (
    <div className="checkbox">
      <input
        type="checkbox"
        id={id}
        checked={checked}
        disabled={disabled}
        aria-describedby={hint ? hintId : undefined}
        onChange={(event) => onChange(event.target.checked)}
      />
      <div>
        <label htmlFor={id}>{label}</label>
        {hint ? (
          <div className="field__hint" id={hintId}>
            {hint}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function FormActions({ children }: { children: ReactNode }) {
  return <div className="page-header__actions">{children}</div>;
}
