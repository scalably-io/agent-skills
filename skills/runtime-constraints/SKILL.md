---
name: runtime-constraints
description: "Use when uncertain whether a tool, package, or library is available in the current agent runtime, before any pip/npm/apt install, when an unfamiliar Bash command fails, or when you need to check what's on PATH before assuming it isn't there. Triggers: what's available, can I install, is X installed, pip install, npm install, package, runtime, blocked path. Not for: actually performing tasks — this is a reference skill, consult it when uncertain what the runtime provides."
license: MIT
metadata:
  source: https://scalably.io/skills/runtime-constraints
  derived_from:
    path: container/skills/runtime-constraints/SKILL.md
    commit: ef174fc3
    date: "2026-09-07"
  triggers: [what tools do I have, can I install, runtime, agent environment, what's available, package install, pip install, npm install, runtime limits]
  not_for: [Actually performing tasks — this is a reference skill only, consult it when uncertain what the runtime provides]
---

# Runtime Constraints

## What it does

Every agent runtime — a container, a sandboxed VM, a CI worker, a bare laptop shell — pre-installs a different set of languages, CLIs, and libraries, and blocks a different set of paths and network calls. Assuming your runtime looks like the one you tested on last time is the single most common cause of a wasted install attempt or a confusing failure. This skill is a discipline, not an inventory: probe before you assume, install to a scratch location instead of polluting the project tree, and treat a blocked path or denied tool as a hard boundary rather than a bug to route around.

## Requirements

- None.

## Inputs and outputs

| | |
|---|---|
| Input | A question — "is X installed", "can I run Y", "why did this command fail" |
| Output | Nothing written to disk. The three probe commands print directly to the terminal: exit code + version/path (available) or a "not found" / `ModuleNotFoundError` (missing) |

## Worked example

Paste into any shell to check for three unrelated things — a CLI binary, a Python library, and a Node module:

```bash
command -v ffmpeg && ffmpeg -version | head -1
python3 -c "import pandas; print(pandas.__version__)"
node -e "console.log(require.resolve('sharp'))"
```

Expected when available: each line prints a path or version string and the command exits 0.

Expected when missing — this is what to look for, not an error to debug:
```
$ python3 -c "import pandas; print(pandas.__version__)"
Traceback (most recent call last):
  ...
ModuleNotFoundError: No module named 'pandas'
```
A `ModuleNotFoundError` / `command not found` / non-zero exit is the runtime telling you the dependency genuinely isn't there — not a sign you did something wrong. Install it (see below) or pick a different approach; don't retry the same import expecting a different answer.

## Procedure

### Discover before you assume

Never assume a tool, package, or library is present because it was on a different machine, a different container image, or last week's session. Three probes cover almost everything:

1. **Is it a CLI on PATH?**
   ```bash
   command -v <tool>        # prints the resolved path, or nothing
   <tool> --version          # confirms it actually runs
   ```
2. **Is it a Python library?**
   ```bash
   python3 -c "import <module>; print(<module>.__version__)"
   ```
   (Not every library exposes `__version__` — if that line errors on the attribute but the `import` itself succeeded, the library is present; drop the `print` and just import.)
3. **Is it a Node package?**
   ```bash
   node -e "console.log(require.resolve('<package>'))"
   ```
4. **If you're inside an agent runtime that exposes MCP tools**, list what the current session actually has connected rather than assuming a tool from a different setup is available — a tool's *name* being familiar to you says nothing about whether *this* session has it wired up.

Run the relevant probe before reaching for `pip install` / `npm install`. A runtime that pre-installs common libraries wastes an install cycle (and sometimes fails outright on a read-only filesystem) when the dependency was there all along; a runtime that doesn't will tell you clearly and quickly.

### Install to a scratch location, not the project tree

If a probe confirms something is genuinely missing and you need it, avoid installing into your working directory when you can help it — many runtimes pre-install common libraries at a system level and expect the project tree to stay clean, and some block writes to it outright. Prefer a scratch/temp location and point the interpreter at it explicitly:

```bash
pip install --target=/tmp/pylibs somepackage
PYTHONPATH=/tmp/pylibs python3 script.py
```

### Prefer built-in network tools over raw HTTP

If your runtime offers dedicated web-fetch/web-search tools (built into the agent framework, or MCP tools for a specific integrated service), prefer them over raw `curl`/`wget` — they typically carry auth headers, retry logic, and caching that a bare request lacks. Raw `curl`/`wget` still works and is a reasonable last resort when nothing else fits, but expect to handle auth, rate limiting, and retries yourself.

For anything JS-rendered, needing form fills, clicks, or logins, use a browser-automation capability (interactive) rather than a plain HTTP fetch. For public read-only page content at scale, a bounded scraping tool (see the `browser-scrape` skill) is usually the better fit than either.

### Respect blocked paths and denied tools

Runtimes commonly fence off certain paths (secrets, host config, another tenant's data) and deny certain destructive operations (irreversible deletes on a connected service) at the policy layer, independent of what your current task is trying to do. If a write, read, or tool call is refused for a path- or policy-based reason, that refusal is the runtime doing its job — it means the operation is genuinely not allowed for you right now, not that you found a bug. Don't try to route around it with a different path, a different tool, or a workaround script; find a different approach or tell the user the operation is blocked and why.

### Audio & video

```bash
# Extract audio from a video file
ffmpeg -i video.mp4 -vn -acodec mp3 /tmp/audio.mp3

# Transcribe via the OpenAI API, if a key is configured
curl -s https://api.openai.com/v1/audio/transcriptions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -F file=@/tmp/audio.mp3 -F model=gpt-4o-transcribe
```

Check whether an API key env var is set before relying on it (`[ -n "$OPENAI_API_KEY" ]` or the language equivalent) rather than assuming every runtime has one configured — and never echo, log, or otherwise surface the value of a secret once you've confirmed it exists.

### Delivering large files

Most chat/file-delivery channels cap a direct file attachment somewhere in the single-digit-to-low-double-digit megabytes. Before assuming a large deliverable (a video, a big export) can be sent directly, check the channel's documented limit. When a file exceeds it, don't try to chunk or compress your way around the cap — publish it somewhere with a real URL instead and hand back the link. For an HTML deliverable specifically, see the `publish-html` skill; for other file types, the same pattern applies: put the file somewhere fetchable over HTTP and send the link, not the bytes.
