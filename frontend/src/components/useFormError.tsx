"use client";

import { useCallback, useRef, useState } from "react";
import { ApiError } from "@/lib/api";

/**
 * How a failed form submission is shown and announced (WCAG 2.1 AA; CLAUDE.md
 * §8). The backend returns one of two shapes on failure:
 *
 * - A `problems: {field, problem}[]` array, from a Pydantic validation error
 *   (a field the browser didn't already stop, e.g. an email with no `@`).
 *   Each named field gets its own message, `aria-invalid` and
 *   `aria-describedby`, and focus moves to the first one.
 * - A single message with no field attribution (a rule the service layer
 *   enforces, e.g. "that email is already registered"). It is shown as a
 *   page-level alert, which receives focus instead, since there is no single
 *   field to blame.
 */
export type FieldErrors = Record<string, string>;

export function useFormError() {
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const alertRef = useRef<HTMLParagraphElement | null>(null);

  const clear = useCallback(() => {
    setError(null);
    setFieldErrors({});
  }, []);

  const fail = useCallback((problem: unknown, form?: HTMLFormElement | null) => {
    const fields: FieldErrors = {};
    let message = "Something went wrong.";
    if (problem instanceof ApiError) {
      message = problem.message;
      for (const p of problem.problems ?? []) {
        fields[p.field] = p.problem;
      }
    }
    setError(message);
    setFieldErrors(fields);
    // Wait a tick so the error text (and the aria-invalid attributes) are in
    // the DOM before anything tries to focus them.
    requestAnimationFrame(() => {
      const firstField = Object.keys(fields)[0];
      const target =
        (firstField && form?.elements.namedItem(firstField)) instanceof HTMLElement
          ? (form!.elements.namedItem(firstField) as HTMLElement)
          : null;
      (target ?? alertRef.current)?.focus();
    });
  }, []);

  /** Spread onto an `<input>`/`<select>`/`<textarea>` named `name`. Pass
   * `hintId` when the field already has a static description below it, so
   * both are announced together. */
  function fieldProps(name: string, hintId?: string) {
    const message = fieldErrors[name];
    const describedBy = [message ? `${name}-error` : null, hintId ?? null]
      .filter(Boolean)
      .join(" ");
    return {
      ...(message ? { "aria-invalid": true as const } : {}),
      ...(describedBy ? { "aria-describedby": describedBy } : {}),
    };
  }

  return { error, fieldErrors, alertRef, clear, fail, fieldProps };
}

/** The message a field's `aria-describedby` points at. Renders nothing if
 * that field has no error. */
export function FieldError({ name, fieldErrors }: { name: string; fieldErrors: FieldErrors }) {
  const message = fieldErrors[name];
  if (!message) return null;
  return (
    <p id={`${name}-error`} className="mt-1 text-sm text-[var(--bad)]">
      {message}
    </p>
  );
}
