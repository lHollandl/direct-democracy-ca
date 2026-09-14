---
name: reference_queries
version: 1
purpose: >
  Turn an umbrella's problem statement and its leading solutions into one to
  three web search queries that would find useful background for the people
  working on it.
inputs:
  umbrella_name: the umbrella's name
  umbrella_statement: the one-paragraph statement of the problem
  community: the community label, e.g. "San Jose (city)"
  dominant_solutions: the current dominant solution texts, one per line
output: >
  A single JSON object and nothing else:
  {"queries": ["...", "..."]}
---

Residents of {{community}} are working on this problem together:

**{{umbrella_name}}** — {{umbrella_statement}}

The solutions currently carrying the most support:

{{dominant_solutions}}

Write one to three web search queries that would find **factual background** a
resident would want before voting: what the local government has already done,
what similar places tried, what a plan of this kind costs, what the law
requires.

Do not write queries that look for opinion pieces, campaign material or
partisan commentary. Residents across the political spectrum will read what
these queries find.

Answer with one JSON object and nothing else:

{"queries": ["first query", "second query"]}
