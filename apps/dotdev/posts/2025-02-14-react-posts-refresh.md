---
title: Rebuilding the notes page as a React-powered timeline
date: 2025-02-14
tags:
  - react
  - flask
  - content-workflow
---

I wanted to make updates to my notes page easier to publish. The new setup reads Markdown files directly from a `posts/` folder and renders them through a React timeline component.

The Flask backend now parses front matter metadata for publish dates and tags, exposes an archive-friendly API, and ships a small word cloud dataset. With everything in Markdown, adding a new story is as simple as dropping a file into version control.
