#!/usr/bin/env python3
"""Browser automation CLI — persistent Chromium via CDP.

Usage:
    python browser.py <command> [args...]

Commands:
    navigate <url>                  Go to a URL
    snapshot                        Accessibility tree with element refs
    click <ref_or_selector>         Click an element
    type <ref_or_selector> <text>   Type into a field
    press_key <key>                 Press a keyboard key
    screenshot [--full-page]        Save a PNG screenshot
    go_back                         Navigate back
    wait <seconds>                  Wait for a duration
    wait_for_text <text>            Wait for text to appear
    close                           Shut down the browser

The browser launches on first use and persists via CDP for subsequent
calls.  Element refs (e.g. e42) come from snapshot output and are valid
until the next snapshot.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

STATE_DIR = Path("/workspace/.browser")
STATE_FILE = STATE_DIR / "state.json"
SCREENSHOTS_DIR = Path("/workspace/screenshots")
CDP_PORT = 9222

# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

def _load_state() -> dict[str, Any]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_state(state: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ---------------------------------------------------------------------------
# Browser lifecycle
# ---------------------------------------------------------------------------

def _find_chromium() -> str:
    """Locate the Playwright-managed Chromium binary."""
    cache = Path.home() / ".cache" / "ms-playwright"
    for chrome in sorted(cache.glob("chromium-*/chrome-linux/chrome"), reverse=True):
        if chrome.is_file() and os.access(chrome, os.X_OK):
            return str(chrome)
    raise FileNotFoundError("Chromium binary not found — run: playwright install chromium")


def _is_browser_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _launch_browser() -> dict[str, Any]:
    """Launch a detached Chromium process with CDP enabled."""
    chrome = _find_chromium()
    proc = subprocess.Popen(
        [
            chrome,
            "--headless=new",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            f"--remote-debugging-port={CDP_PORT}",
            "--remote-debugging-address=127.0.0.1",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    # Give Chromium a moment to bind the CDP port.
    time.sleep(1.5)
    if proc.poll() is not None:
        raise RuntimeError("Chromium exited immediately — check container resources")
    state = {"pid": proc.pid, "cdp_url": f"http://127.0.0.1:{CDP_PORT}"}
    _save_state(state)
    return state


async def _connect(pw: Any) -> tuple[Any, Any]:
    """Connect to the running Chromium via CDP, launching if needed."""
    state = _load_state()
    pid = state.get("pid")

    if pid and _is_browser_alive(pid):
        cdp_url = state["cdp_url"]
    else:
        state = _launch_browser()
        cdp_url = state["cdp_url"]

    browser = await pw.chromium.connect_over_cdp(cdp_url)
    contexts = browser.contexts
    if contexts and contexts[0].pages:
        page = contexts[0].pages[0]
    else:
        ctx = await browser.new_context(viewport={"width": 1280, "height": 720})
        page = await ctx.new_page()

    page.set_default_timeout(30_000)
    page.set_default_navigation_timeout(30_000)
    return browser, page


# ---------------------------------------------------------------------------
# Accessibility snapshot + ref tracking
# ---------------------------------------------------------------------------

_ref_counter: int = 0
_ref_map: dict[str, dict[str, str]] = {}


def _build_tree(node: dict[str, Any], indent: int = 0) -> list[str]:
    """Recursively format the accessibility tree with ref annotations."""
    global _ref_counter
    lines: list[str] = []
    role = node.get("role", "")

    # Skip generic/redundant nodes but keep their children
    skip_roles = {"none", "generic", "InlineTextBox", "LineBreak"}
    if role in skip_roles:
        for child in node.get("children", []):
            lines.extend(_build_tree(child, indent))
        return lines

    _ref_counter += 1
    ref = f"e{_ref_counter}"
    name = node.get("name", "")
    value = node.get("value", "")

    parts = [f"{'  ' * indent}- {role}"]
    if name:
        display_name = name if len(name) <= 80 else name[:77] + "..."
        parts.append(f'"{display_name}"')
    if value:
        display_val = value if len(value) <= 60 else value[:57] + "..."
        parts.append(f'[value="{display_val}"]')

    # Extra attributes
    for attr in ("level", "checked", "pressed", "expanded", "selected"):
        if attr in node:
            parts.append(f"[{attr}={node[attr]}]")

    parts.append(f"[ref={ref}]")
    lines.append(" ".join(parts))

    _ref_map[ref] = {"role": role, "name": name}

    for child in node.get("children", []):
        lines.extend(_build_tree(child, indent + 1))

    return lines


def _resolve_selector(page: Any, selector: str) -> Any:
    """Resolve a ref, text= selector, or CSS selector to a locator."""
    if selector in _ref_map:
        info = _ref_map[selector]
        return page.get_by_role(info["role"], name=info["name"])
    if selector.startswith("text="):
        return page.get_by_text(selector[5:])
    return page.locator(selector)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

async def cmd_navigate(page: Any, args: list[str]) -> dict[str, Any]:
    url = args[0] if args else ""
    if not url:
        return {"error": "url required"}
    resp = await page.goto(url, wait_until="domcontentloaded")
    return {
        "url": page.url,
        "title": await page.title(),
        "status": resp.status if resp else None,
    }


async def cmd_snapshot(page: Any, _args: list[str]) -> dict[str, Any]:
    global _ref_counter, _ref_map
    _ref_counter = 0
    _ref_map = {}

    tree = await page.accessibility.snapshot()  # type: ignore[union-attr]
    if not tree:
        return {"snapshot": "(empty page)", "url": page.url}

    lines = _build_tree(tree)
    snapshot_text = "\n".join(lines)

    # Persist ref map so subsequent calls in separate process can use it
    state = _load_state()
    state["ref_map"] = _ref_map
    _save_state(state)

    return {"snapshot": snapshot_text, "url": page.url, "title": await page.title()}


async def cmd_click(page: Any, args: list[str]) -> dict[str, Any]:
    selector = args[0] if args else ""
    if not selector:
        return {"error": "selector required"}
    locator = _resolve_selector(page, selector)
    await locator.click()
    return {"clicked": True, "selector": selector}


async def cmd_type(page: Any, args: list[str]) -> dict[str, Any]:
    if len(args) < 2:
        return {"error": "usage: type <selector> <text> [--submit]"}
    selector, text = args[0], args[1]
    submit = "--submit" in args[2:]
    locator = _resolve_selector(page, selector)
    await locator.fill(text)
    if submit:
        await locator.press("Enter")
    return {"typed": True, "selector": selector}


async def cmd_press_key(page: Any, args: list[str]) -> dict[str, Any]:
    key = args[0] if args else ""
    if not key:
        return {"error": "key required"}
    await page.keyboard.press(key)
    return {"pressed": True, "key": key}


async def cmd_screenshot(page: Any, args: list[str]) -> dict[str, Any]:
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    full_page = "--full-page" in args
    ts = time.strftime("%Y%m%d-%H%M%S")
    path = SCREENSHOTS_DIR / f"screenshot-{ts}.png"
    await page.screenshot(path=str(path), full_page=full_page)
    return {"path": str(path), "url": page.url}


async def cmd_go_back(page: Any, _args: list[str]) -> dict[str, Any]:
    await page.go_back(wait_until="domcontentloaded")
    return {"url": page.url, "title": await page.title()}


async def cmd_wait(page: Any, args: list[str]) -> dict[str, Any]:
    seconds = float(args[0]) if args else 1.0
    seconds = min(seconds, 30.0)
    await asyncio.sleep(seconds)
    return {"waited": True, "seconds": seconds}


async def cmd_wait_for_text(page: Any, args: list[str]) -> dict[str, Any]:
    text = " ".join(args) if args else ""
    if not text:
        return {"error": "text required"}
    await page.get_by_text(text).wait_for(state="visible", timeout=15_000)
    return {"found": True, "text": text}


async def cmd_close(_page: Any, _args: list[str]) -> dict[str, Any]:
    state = _load_state()
    pid = state.get("pid")
    if pid and _is_browser_alive(pid):
        os.kill(pid, signal.SIGTERM)
    if STATE_FILE.exists():
        STATE_FILE.unlink()
    return {"closed": True}


COMMANDS = {
    "navigate": cmd_navigate,
    "snapshot": cmd_snapshot,
    "click": cmd_click,
    "type": cmd_type,
    "press_key": cmd_press_key,
    "screenshot": cmd_screenshot,
    "go_back": cmd_go_back,
    "wait": cmd_wait,
    "wait_for_text": cmd_wait_for_text,
    "close": cmd_close,
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        return

    command = sys.argv[1]
    args = sys.argv[2:]

    if command not in COMMANDS:
        print(json.dumps({"error": f"unknown command: {command}"}))
        sys.exit(1)

    # Load ref map from state so refs survive across process invocations
    global _ref_map
    state = _load_state()
    _ref_map = state.get("ref_map", {})

    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        try:
            browser, page = await _connect(pw)
        except Exception as e:
            # If connection fails, try a fresh launch
            if STATE_FILE.exists():
                STATE_FILE.unlink()
            _launch_browser()
            browser, page = await _connect(pw)

        try:
            result = await COMMANDS[command](page, args)
            print(json.dumps(result, indent=2))
        except Exception as e:
            print(json.dumps({"error": str(e)}))
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
