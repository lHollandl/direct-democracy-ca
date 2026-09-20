import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // `next dev` otherwise auto-generates AGENTS.md and CLAUDE.md at the repo
  // root, and Claude Code reads any CLAUDE.md it finds as instructions
  // (change/02, C2-11(b)).
  agentRules: false,
};

export default nextConfig;
