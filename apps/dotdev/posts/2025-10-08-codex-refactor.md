---
title: Refactoring my site with Codex in hours instead of days
date: 2025-10-08
tags:
  - codex
  - productivity
  - automation
---

Today I paired with OpenAI Codex to overhaul my personal website, and the entire refresh came together in a few focused sessions instead of the multi-day sprint I expected.

We migrated the old notes page into a Markdown-driven posts timeline, complete with a React front end, archive browser, and automated word cloud. Codex handled the heavy lifting: wiring up new Flask APIs, designing the React components, tightening responsive styles, and even refining the deployment setup to keep Docker builds happy.

The most surprising part was how quickly we iterated. I could drop new `.md` files into the `posts/` directory and immediately see the updates. By the time we finished, the tests were passing, the docs were refreshed, and the site felt far more maintainable. Collaboration with Codex turned what would normally be a weekend project into a single productive day.
