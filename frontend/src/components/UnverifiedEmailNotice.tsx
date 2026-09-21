"use client";

import { useState } from "react";
import { ApiError, post } from "@/lib/api";

type ResendOut = { message: string; demo_link?: string | null };

/** ARCHITECTURE.md §4, §6 — shown wherever an unverified account is told to
 * confirm its email, with the control that actually lets them ask for a new
 * link (FX-03). Reused on the site-wide banner and at step 1 of "New post"
 * (FX-02), so the two never drift apart on what "Send me a new link" does. */
export function UnverifiedEmailNotice() {
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [demoLink, setDemoLink] = useState<string | null>(null);

  async function resend() {
    setStatus("sending");
    setFeedback(null);
    setDemoLink(null);
    try {
      const body = await post<ResendOut>("/me/resend-verification");
      setStatus("sent");
      setFeedback(body.message);
      setDemoLink(body.demo_link ?? null);
    } catch (problem) {
      setStatus("error");
      setFeedback(
        problem instanceof ApiError ? problem.message : "Could not send a new link just now.",
      );
    }
  }

  return (
    <span className="block">
      Confirm your email address before posting, voting or commenting. The
      link is in the message we sent when you signed up.{" "}
      <button
        type="button"
        className="btn px-2 py-1 text-sm"
        onClick={() => void resend()}
        disabled={status === "sending"}
      >
        {status === "sending" ? "Sending…" : "Send me a new link"}
      </button>
      {feedback ? (
        <span role="status" className="mt-1 block text-sm">
          {feedback}
        </span>
      ) : null}
      {demoLink ? (
        <span className="mt-1 block text-sm">
          Demo mode — no email was sent. <a href={demoLink}>Confirm here</a>.
        </span>
      ) : null}
    </span>
  );
}
