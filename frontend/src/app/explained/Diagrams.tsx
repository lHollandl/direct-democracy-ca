"use client";

/**
 * Two inline SVG diagrams for /explained (C1-06). Each carries a `<title>`
 * and `<desc>` for screen readers and is followed by an ordered-list
 * equivalent that carries the full text — the diagram itself only needs
 * short labels, so it stays legible at 320px wide with images off (CLAUDE.md
 * §8, WCAG 2.1 AA). Diagram 2's marker positions come from the live settings
 * (never a typed-in day count), placed against an illustrative 30-day month.
 */

import { cycleRuleWords, type SettingsMap } from "@/content/explainers";

const ARROW_MARKER = (
  <defs>
    <marker id="explained-arrow" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
      <path d="M0,0 L8,4 L0,8 z" fill="currentColor" />
    </marker>
  </defs>
);

export const PATH_STEPS = [
  {
    label: "Post",
    text: "A citizen submits a post: a problem and at least one proposed solution.",
  },
  {
    label: "Filed",
    text: "The post is filed under an umbrella — by AI suggestion, or the author's own pick.",
  },
  {
    label: "Workshop",
    text: "Neighbors work on it in the umbrella's workshop: solutions, amendments, discussion.",
  },
  {
    label: "Jury review",
    text: "A jury of residents drawn at random reviews what qualified, and may hold an item back, in public, with a reason.",
  },
  {
    label: "Ballot",
    text: "The community votes on what remains — one vote each, counted the same.",
  },
  {
    label: "Published",
    text: "The result is published as one public document with a fingerprint anyone can check.",
  },
  {
    label: "Representatives",
    text: "It is sent to the representatives who decide at that level of government.",
  },
];

export function PathOfAProblemDiagram() {
  const boxW = 220;
  const boxH = 40;
  const gapY = 22;
  const x = 16;
  const n = PATH_STEPS.length;
  const svgW = boxW + 100;
  const svgH = 16 + n * boxH + (n - 1) * gapY + 16;
  const workshopIndex = 2;
  const lastIndex = n - 1;
  const lastY = 16 + lastIndex * (boxH + gapY) + boxH / 2;
  const workshopY = 16 + workshopIndex * (boxH + gapY) + boxH / 2;
  const loopX = x + boxW + 60;

  return (
    <svg
      viewBox={`0 0 ${svgW} ${svgH}`}
      role="img"
      aria-labelledby="path-diagram-title path-diagram-desc"
      className="mx-auto h-auto w-full max-w-sm text-[var(--foreground)]"
    >
      <title id="path-diagram-title">The path of a problem</title>
      <desc id="path-diagram-desc">
        A post moves from being filed under an umbrella, through the
        workshop, a jury review, a ballot, and a published result, to
        delivery to representatives, and then back to the workshop for the
        next round. The full text of each step follows this diagram as an
        ordered list.
      </desc>
      {ARROW_MARKER}
      {PATH_STEPS.map((step, i) => {
        const y = 16 + i * (boxH + gapY);
        return (
          <g key={step.label}>
            <rect
              x={x}
              y={y}
              width={boxW}
              height={boxH}
              rx={8}
              fill="none"
              stroke="currentColor"
            />
            <text
              x={x + boxW / 2}
              y={y + boxH / 2}
              textAnchor="middle"
              dominantBaseline="middle"
              fontSize={13}
            >
              {i + 1}. {step.label}
            </text>
            {i < n - 1 ? (
              <line
                x1={x + boxW / 2}
                y1={y + boxH}
                x2={x + boxW / 2}
                y2={y + boxH + gapY}
                stroke="currentColor"
                markerEnd="url(#explained-arrow)"
              />
            ) : null}
          </g>
        );
      })}
      <path
        d={`M ${x + boxW} ${lastY} C ${loopX} ${lastY}, ${loopX} ${workshopY}, ${x + boxW} ${workshopY}`}
        fill="none"
        stroke="currentColor"
        strokeDasharray="4 3"
        markerEnd="url(#explained-arrow)"
      />
      <text x={loopX} y={(lastY + workshopY) / 2} textAnchor="middle" fontSize={10}>
        back to the
      </text>
      <text x={loopX} y={(lastY + workshopY) / 2 + 12} textAnchor="middle" fontSize={10}>
        workshop
      </text>
    </svg>
  );
}

export function aMonthSteps(settings: SettingsMap) {
  const juryReviewDays = Number(settings.jury_review_days);
  const ballotWindowDays = Number(settings.ballot_window_days);
  return [
    {
      label: "Workshop",
      text: "The workshop never closes — solutions, amendments and discussion continue all month, every month.",
    },
    {
      label: "Jury draw expected",
      text: `A jury is expected to be drawn ${juryReviewDays} day${juryReviewDays === 1 ? "" : "s"} before the ballot is expected to open.`,
    },
    {
      label: "Ballot open",
      text: `The ballot is expected to open on ${cycleRuleWords(settings.cycle_open_rule)} and stay open ${ballotWindowDays} day${ballotWindowDays === 1 ? "" : "s"}.`,
    },
    {
      label: "Result published",
      text: "When the ballot closes, the result is published as one public document.",
    },
  ];
}

export function AMonthDiagram({ settings }: { settings: SettingsMap }) {
  const juryReviewDays = Number(settings.jury_review_days);
  const ballotWindowDays = Number(settings.ballot_window_days);
  const totalDays = Math.max(30, juryReviewDays + ballotWindowDays + 10);
  const ballotStartDay = totalDays - ballotWindowDays - 2;
  const ballotEndDay = ballotStartDay + ballotWindowDays;
  const juryDrawDay = Math.max(0, ballotStartDay - juryReviewDays);

  const marginX = 20;
  const axisW = 300;
  const axisY = 70;
  const dayX = (day: number) => marginX + (day / totalDays) * axisW;

  return (
    <svg
      viewBox={`0 0 ${axisW + marginX * 2} 130`}
      role="img"
      aria-labelledby="month-diagram-title month-diagram-desc"
      className="mx-auto h-auto w-full max-w-sm text-[var(--foreground)]"
    >
      <title id="month-diagram-title">A month</title>
      <desc id="month-diagram-desc">
        The workshop runs across the whole month. A jury draw is expected a
        few days before the ballot is expected to open on{" "}
        {cycleRuleWords(settings.cycle_open_rule)}; the ballot stays open for
        its window, and the result is published when it closes. The full
        text follows this diagram as an ordered list.
      </desc>
      {ARROW_MARKER}
      {/* Workshop: spans the whole month */}
      <line
        x1={dayX(0)}
        y1={axisY}
        x2={dayX(totalDays)}
        y2={axisY}
        stroke="currentColor"
        strokeWidth={4}
      />
      <text x={marginX} y={axisY - 10} fontSize={12}>
        Workshop — all month
      </text>

      {/* Ballot window: highlighted band */}
      <rect
        x={dayX(ballotStartDay)}
        y={axisY - 6}
        width={dayX(ballotEndDay) - dayX(ballotStartDay)}
        height={12}
        fill="currentColor"
      />
      <text x={dayX(ballotStartDay)} y={axisY + 24} fontSize={11}>
        Ballot open
      </text>

      {/* Jury draw marker */}
      <circle cx={dayX(juryDrawDay)} cy={axisY} r={4} fill="currentColor" />
      <text x={dayX(juryDrawDay)} y={axisY - 22} fontSize={10} textAnchor="middle">
        Jury draw
      </text>
      <text x={dayX(juryDrawDay)} y={axisY - 10} fontSize={10} textAnchor="middle">
        expected
      </text>

      {/* Result published marker */}
      <circle cx={dayX(ballotEndDay)} cy={axisY} r={4} fill="currentColor" />
      <text x={dayX(ballotEndDay)} y={axisY + 40} fontSize={10} textAnchor="middle">
        Result
      </text>
      <text x={dayX(ballotEndDay)} y={axisY + 52} fontSize={10} textAnchor="middle">
        published
      </text>
    </svg>
  );
}
