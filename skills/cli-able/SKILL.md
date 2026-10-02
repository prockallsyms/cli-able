---
name: cli-able
description: Use when the user wants a command-line tool for a website, web app, or HTTP API (REST, GraphQL, OpenAPI spec, or a site with no public API) so it can be scripted, piped, or called by agents. Triggers include "make a CLI for X", "wrap this API", "turn this site into a command", or "I want to query X from the terminal".
---

# cli-able

Build a small, reliable CLI that wraps a website or API the user has legitimate access to. The result should work equally well for a human at a terminal and for an agent calling it from a shell.

Use the **most stable interface available** and the **fewest moving parts**. One file, standard library, real requests verified before code is written.

## 1. Scope (ask only what you can't discover)

Establish:
- **Target**: base URL, docs URL, or spec file.
- **Jobs**: the 3–7 operations the user actually needs ("list my open invoices", "search products", "post a message"). Build those, not the entire API.
- **Auth**: what credentials they have (API key, OAuth token, username/password, browser session).
- **Runtime**: default to Python 3 stdlib. Use Node 18+ (built-in `fetch`, `util.parseArgs`) or the user's language if the user prefers it or the project already uses it.
- **Location**: default to `./<name>-cli/` in the current directory.

Before building, check whether an official CLI already exists (`gh`, `stripe`, `aws`, `gcloud`, `vercel`...). If one covers the jobs, tell the user and stop unless they still want a custom one.

## 2. Recon: find the best interface

Work down this list and stop at the first one that covers the jobs:

1. **Machine-readable spec.** Try `/openapi.json`, `/openapi.yaml`, `/swagger.json`, `/v3/api-docs`, `/api-docs`, `/.well-known/openapi`, plus links from the docs. For GraphQL, run an introspection query against `/graphql`.
2. **Official API docs.** Read the endpoints for the jobs: auth scheme, pagination style, rate limits, error format.
3. **The site's own JSON API.** Most modern sites call a JSON backend. Find it:
   - Ask the user to export a HAR file or copy a request as cURL from browser DevTools (Network tab, filter Fetch/XHR) while doing the job by hand. This is the fastest route, and the requests come with working auth.
   - If you have a browser tool (Playwright, Chrome DevTools MCP), capture the network requests yourself.
   - Otherwise fetch the page and look for endpoints in inline scripts (`fetch(`, `/api/`, `graphql`), embedded state (`__NEXT_DATA__`, `__NUXT__`, `window.__INITIAL_STATE__`), `application/ld+json`, RSS/Atom feeds, and `sitemap.xml`.
4. **HTML scraping.** Only when no JSON exists. Use stable hooks (`id`, `data-*`, semantic tags), not generated class names. In Python, stdlib `html.parser` is enough for simple pages. Add a dependency (BeautifulSoup, selectolax) only if parsing gets hairy.
5. **Headless browser.** Only if content is JS-rendered and none of the above works. It is slow and brittle, so tell the user that's the tradeoff.

**Verify with a real request before writing any code.** `curl` each endpoint you plan to use, save one sample response per endpoint, and confirm the fields you need are there. A wrong guess about response shape is the most common failure.

## 3. Auth

- Read secrets from environment variables (`<NAME>_TOKEN`, `<NAME>_API_KEY`). An optional config file in `~/.config/<name>/config.json` is fine; create it with `0600` permissions.
- For cookie/session sites, add a `login` command that stores the session in that config dir, or let the user paste a cookie header copied from DevTools.
- For OAuth, use device flow if the provider supports it. If it doesn't, accept a pasted token.
- Never hardcode, print, or log secrets. Redact them in `--verbose` output. Never write them inside the project directory where they could get committed.

## 4. Command design

```
<name> <resource> <verb> [args] [flags]     # e.g. acme invoices list --status open
<name> <verb> [args]                         # fine when there are only a few commands
<name> api <METHOD> <path> [--data JSON]     # raw escape hatch, like `gh api`
```

Conventions (the template implements all of them):
- **stdout is data, stderr is everything else.** Progress, warnings, and errors go to stderr so pipes stay clean.
- **`--json`** prints raw JSON (an array or object, or one object per line with `--jsonl` for streams). Without it, print a compact human-readable view. Agents will use `--json`.
- **Exit codes**: `0` success, `1` runtime/API error, `2` usage error. Error messages include the HTTP status and the API's own message.
- **`--help` on every command**, with one example per command.
- **Pagination**: `--limit N` (sensible default) and `--all` to follow every page.
- **Mutations**: `--dry-run` prints the request it would send. Destructive operations (delete, cancel, send) require `--yes` when stdin isn't a TTY, and prompt otherwise.
- **Config overrides**: `<NAME>_BASE_URL` env var so the tool can point at staging or a mock.
- Use names from the domain ("invoices", "channels"), not endpoint paths.

## 5. Implement

Start from [`template.py`](template.py) in this skill's directory. It's a single-file, zero-dependency Python CLI with HTTP and retries, auth from env, JSON/human output, pagination, `--dry-run`, and the `api` escape hatch. Copy it, rename it, and replace the example commands. If the target runtime is another language, port its structure and conventions.

Requirements:
- Timeouts on every request (default 30s).
- Retry on 429 and 5xx with exponential backoff, honoring `Retry-After`. Don't retry other 4xx.
- Send a descriptive `User-Agent` (`<name>-cli/0.1`).
- Respect documented rate limits. For scraping, keep to about one request per second unless told otherwise.
- Keep it in one file until it passes roughly 500 lines.

If you need third-party deps in Python, declare them with inline script metadata (PEP 723) and run via `uv run`. That way the tool stays a single file:
```python
# /// script
# requires-python = ">=3.10"
# dependencies = ["beautifulsoup4"]
# ///
```

## 6. Verify

Don't report success until each of these has been run and its output checked:
1. `<name> --help` and `<name> <command> --help` for every command.
2. Each read command against the real service, with and without `--json`. Pipe `--json` through `python -m json.tool` (or `jq`) to prove it's valid.
3. Each mutating command with `--dry-run` first. Run it for real only with the user's OK, on test data if possible.
4. The failure paths: missing token (clean message, exit 1), bad argument (exit 2), and a 404.

Leave one runnable smoke test (`test_<name>.sh` or `test_<name>.py`) that runs the read-only commands and checks the exit codes.

## 7. Ship

- Make it executable and put it on PATH. Pick one: `chmod +x` and symlink into `~/.local/bin`, `uv tool install`/`pipx install` if packaged, `npm link` for Node. On Windows, a `<name>.cmd` shim containing `@python "%~dp0<name>.py" %*` works.
- Write a short README: install, auth env vars, one example per command.
- **Offer to write an agent skill for the new CLI**: a `SKILL.md` with frontmatter (`name`, `description: Use when...`) listing the commands, `--json` usage, and required env vars, so the user's agents know when and how to call it.

## Boundaries

- Only wrap services and accounts the user is authorized to use. Respect Terms of Service and `robots.txt` for scraping.
- Don't build tools that defeat CAPTCHAs, paywalls, bot protection, or access controls. If you hit one, stop and tell the user. The fix is an official API or their own authenticated session.
- Don't mass-harvest personal data.
