"use client";

import { useRef, useState } from "react";
import { post } from "@/lib/api";
import VoteButtons from "@/components/VoteButtons";
import { Empty, Notice } from "@/components/ui";
import { FieldError, useFormError } from "@/components/useFormError";

export type Comment = {
  id: number;
  author: string;
  text: string;
  depth: number;
  net_score: number;
  my_vote: number | null;
  created_at: string;
  edited: boolean;
  removed: boolean;
  replies: Comment[];
};

export default function Comments({
  targetType,
  targetId,
  comments,
  canWrite,
  onPosted,
}: {
  targetType: "umbrella" | "solution";
  targetId: number;
  comments: Comment[];
  canWrite: boolean;
  onPosted: () => void;
}) {
  return (
    <div>
      {canWrite ? (
        <CommentForm targetType={targetType} targetId={targetId} onPosted={onPosted} />
      ) : null}
      {comments.length === 0 ? (
        <div className="mt-3">
          <Empty>Nobody has said anything here yet.</Empty>
        </div>
      ) : (
        <ol className="mt-3 space-y-3">
          {comments.map((comment) => (
            <CommentItem
              key={comment.id}
              comment={comment}
              targetType={targetType}
              targetId={targetId}
              canWrite={canWrite}
              onPosted={onPosted}
            />
          ))}
        </ol>
      )}
    </div>
  );
}

function CommentItem({
  comment,
  targetType,
  targetId,
  canWrite,
  onPosted,
}: {
  comment: Comment;
  targetType: "umbrella" | "solution";
  targetId: number;
  canWrite: boolean;
  onPosted: () => void;
}) {
  const [replying, setReplying] = useState(false);
  return (
    <li className="card p-3" style={{ marginLeft: `${comment.depth * 1}rem` }}>
      <p className="text-sm font-medium">{comment.author}</p>
      <p className="mt-1 whitespace-pre-line">{comment.text}</p>
      <p className="mt-1 text-xs text-[var(--muted)]">
        {new Date(comment.created_at).toLocaleString()}
        {comment.edited ? " · edited" : ""}
      </p>
      <div className="mt-2 flex flex-wrap items-center gap-3">
        {comment.removed ? null : (
          <VoteButtons
            targetType="comment"
            targetId={comment.id}
            netScore={comment.net_score}
            myVote={comment.my_vote}
            label={`the comment by ${comment.author}`}
          />
        )}
        {canWrite && !comment.removed ? (
          <button
            type="button"
            className="btn px-2 py-1 text-sm"
            onClick={() => setReplying(!replying)}
          >
            {replying ? "Cancel" : "Reply"}
          </button>
        ) : null}
      </div>
      {replying ? (
        <CommentForm
          targetType={targetType}
          targetId={targetId}
          parentId={comment.id}
          onPosted={() => {
            setReplying(false);
            onPosted();
          }}
        />
      ) : null}
      {comment.replies.length ? (
        <ol className="mt-3 space-y-3">
          {comment.replies.map((reply) => (
            <CommentItem
              key={reply.id}
              comment={reply}
              targetType={targetType}
              targetId={targetId}
              canWrite={canWrite}
              onPosted={onPosted}
            />
          ))}
        </ol>
      ) : null}
    </li>
  );
}

function CommentForm({
  targetType,
  targetId,
  parentId,
  onPosted,
}: {
  targetType: "umbrella" | "solution";
  targetId: number;
  parentId?: number;
  onPosted: () => void;
}) {
  const [text, setText] = useState("");
  const { error, fieldErrors, alertRef, clear, fail, fieldProps } = useFormError();
  const [busy, setBusy] = useState(false);
  const fieldId = `comment-${targetType}-${targetId}-${parentId ?? "root"}`;
  const formRef = useRef<HTMLFormElement>(null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    clear();
    setBusy(true);
    try {
      await post("/comments", {
        target_type: targetType,
        target_id: targetId,
        parent_id: parentId ?? null,
        text,
      });
      setText("");
      onPosted();
    } catch (problem) {
      fail(problem, formRef.current);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form ref={formRef} onSubmit={submit} className="mt-3" noValidate>
      <label htmlFor={fieldId} className="block text-sm font-medium">
        {parentId ? "Your reply" : "Add to the discussion"}
      </label>
      <textarea
        id={fieldId}
        name="text"
        className="field mt-1"
        rows={3}
        maxLength={2000}
        required
        value={text}
        onChange={(e) => setText(e.target.value)}
        {...fieldProps("text")}
      />
      <FieldError name="text" fieldErrors={fieldErrors} />
      {error ? (
        <div className="mt-1">
          <Notice kind="bad" alertRef={alertRef}>
            {error}
          </Notice>
        </div>
      ) : null}
      <button type="submit" className="btn mt-2" disabled={busy}>
        {busy ? "Posting…" : "Post"}
      </button>
    </form>
  );
}
