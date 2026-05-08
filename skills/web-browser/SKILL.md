---
name: web-browser
description: Browse the web with Playwright — navigate pages, read content via accessibility snapshots, interact with forms, and capture screenshots
user_invocable: true
---

# Web Browser

You have a browser automation script at `/workspace/.claude/skills/web-browser/scripts/browser.py`. It wraps a persistent headless Chromium instance. Run commands via Bash.

## Workflow

1. **Navigate** to a URL:
   ```
   python /workspace/.claude/skills/web-browser/scripts/browser.py navigate "https://example.com"
   ```

2. **Snapshot** the page to understand its structure:
   ```
   python /workspace/.claude/skills/web-browser/scripts/browser.py snapshot
   ```
   Returns an accessibility tree with element refs (e.g., `[ref=e42]`). Use these refs in click/type.

3. **Interact** with elements using refs from the snapshot:
   ```
   python /workspace/.claude/skills/web-browser/scripts/browser.py click e42
   python /workspace/.claude/skills/web-browser/scripts/browser.py type e15 "hello@example.com"
   ```

4. **Screenshot** for visual verification:
   ```
   python /workspace/.claude/skills/web-browser/scripts/browser.py screenshot
   ```
   Use the Read tool to view the saved PNG at the returned path.

## Commands

- `navigate <url>` — go to a URL, waits for DOM content loaded
- `snapshot` — get accessibility tree with `[ref=eN]` element refs
- `click <ref_or_selector>` — click an element
- `type <ref_or_selector> <text> [--submit]` — type into a field, optionally press Enter
- `press_key <key>` — press a key (Enter, Tab, Escape, ArrowDown, etc.)
- `screenshot [--full-page]` — save PNG to `/workspace/screenshots/`
- `go_back` — browser back button
- `wait <seconds>` — wait for a duration (max 30s)
- `wait_for_text <text>` — wait for text to appear on page
- `close` — shut down the browser process

## Selectors

Commands that take a selector accept three formats:

1. **Snapshot ref** (preferred): `e42` — from a previous snapshot's `[ref=e42]`
2. **Text selector**: `text=Submit` — matches visible text
3. **CSS selector**: `button.primary` — standard CSS

## Key Principles

- Always snapshot before interacting. The snapshot shows what's on the page and gives you element refs.
- Use refs from the most recent snapshot. Refs reset on each snapshot call.
- Snapshot after each interaction to see the result and get updated refs.
- For dynamic content, use `wait_for_text "Expected text"` before snapshotting.
- The browser launches automatically on first use and stays alive across calls. No setup needed.
- Screenshots save to `/workspace/screenshots/`. Use the Read tool to view them.
- For pages requiring authentication, navigate to the login page and use type/click to log in.
