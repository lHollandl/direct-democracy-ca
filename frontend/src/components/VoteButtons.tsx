"use client";

import { useState } from "react";
import { ApiError, del, put } from "@/lib/api";

type Result = { net_score: number; [key: string]: unknown };

export default function VoteButtons({
  targetType,
  targetId,
  netScore,
  myVote,
  label,
  onChanged,
}: {
  targetType: "solution" | "amendment" | "comment";
  targetId: number;
  netScore: number;
  myVote: number | null;
  label: string;
  onChanged?: (result: Result) => void;
}) {
  const [score, setScore] = useState(netScore);
  const [vote, setVote] = useState<number | null>(myVote);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function cast(direction: 1 | -1) {
    setError(null);
    setBusy(true);
    try {
      const body =
        vote === direction
          ? await del<Result>("/votes", { target_type: targetType, target_id: targetId })
          : await put<Result>("/votes", {
              target_type: targetType,
              target_id: targetId,
              direction,
            });
      setScore(body.net_score);
      setVote(vote === direction ? null : direction);
      onChanged?.(body);
    } catch (problem) {
      setError(problem instanceof ApiError ? problem.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        className="btn px-2 py-1 text-sm"
        aria-pressed={vote === 1}
        aria-label={`Support ${label}`}
        disabled={busy}
        onClick={() => void cast(1)}
      >
        <span aria-hidden="true">▲</span> Support
      </button>
      <span className="min-w-8 text-center font-bold" aria-live="polite">
        <span className="sr-only">Net score for {label}: </span>
        {score}
      </span>
      <button
        type="button"
        className="btn px-2 py-1 text-sm"
        aria-pressed={vote === -1}
        aria-label={`Object to ${label}`}
        disabled={busy}
        onClick={() => void cast(-1)}
      >
        <span aria-hidden="true">▼</span> Object
      </button>
      {error ? (
        <span role="alert" className="text-sm text-[var(--bad)]">{error}</span>
      ) : null}
    </div>
  );
}
