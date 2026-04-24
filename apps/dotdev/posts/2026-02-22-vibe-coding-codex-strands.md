---
title: Shipping Homi fast with vibe coding, Codex, and Strands
date: 2026-02-22
tags:
  - codex
  - strands
  - vibe-coding
  - ai-agents
  - productivity
---

This week I shipped a working agent UI much faster than I normally would by leaning into vibe coding with Codex and Strands.

I started with a simple terminal loop, then iterated quickly with Codex to add a real Textual interface, provider-aware configuration, better response formatting, and practical defaults for tools like calculator, current time, and HTTP requests. Instead of debating architecture for days, I moved in tight loops: request change, review diff, run checks, repeat.

Strands made the agent layer straightforward. I could focus on user experience while still keeping the backend flexible enough to swap model providers later. The combination worked well: Codex accelerated implementation, and Strands kept the core agent design clean.

The key lesson for me: vibe coding is most effective when it is still disciplined. I kept changes small, validated continuously, and documented configuration clearly so the result stayed maintainable.
