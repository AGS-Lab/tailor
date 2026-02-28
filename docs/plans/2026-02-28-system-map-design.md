# Design: Living Documentation System Map

**Date**: 2026-02-28
**Status**: Implemented

## Problem

Docs were written hastily ("YOLO") and are outdated. Team members and AI assistants across different IDEs (Claude Code, Antigravity, etc.) need shared, accurate context about both the current state of the codebase and where it's heading.

## Decision

Layered hub system (Option C):
- `CLAUDE.md` — compact AI entry point, pointers + update protocol
- `docs/system/VISION.md` — what Tailor is, principles, settled decisions, direction
- `docs/system/ARCHITECTURE.md` — accurate current state of all three layers
- `docs/system/INCONSISTENCIES.md` — surfaced issues from audit, living triage list

## Rationale

- Small entry point (CLAUDE.md) fits any AI's context window
- Deep dives available on demand via pointers
- Clear update rules reduce drift over time
- Inconsistencies tracked separately so they don't pollute architecture docs
- Works across any tool that reads markdown

## Audit Findings

13 inconsistencies surfaced during the initial audit. See `docs/system/INCONSISTENCIES.md`.
Critical: IC-001 (config write uses JSON instead of TOML — causes data corruption).

## Maintenance

Primarily AI-maintained. Humans and AIs both follow the update protocol in CLAUDE.md.
