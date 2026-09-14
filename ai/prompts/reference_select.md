---
name: reference_select
version: 1
purpose: >
  Pick the most useful search results for an umbrella and write one plain
  sentence per pick saying why it is relevant.
inputs:
  umbrella_name: the umbrella's name
  umbrella_statement: the one-paragraph statement of the problem
  max_picks: the most references that may be picked
  results: the search results, numbered, as "n | title | url | snippet"
output: >
  A single JSON object and nothing else:
  {"picks": [{"result_number": <int>, "why": "<one sentence>"}]}
---

Residents are working on this problem:

**{{umbrella_name}}** — {{umbrella_statement}}

Here are web search results. Pick at most {{max_picks}} that a resident would
genuinely find useful before voting, and say in one plain sentence why each one
is relevant. Prefer government sources, public data and news reporting over
advocacy. Skip anything partisan, anything selling something, and anything that
does not actually concern this problem. Picking fewer is better than padding.

{{results}}

Answer with one JSON object and nothing else:

{"picks": [{"result_number": 3, "why": "One plain sentence."}]}
