#!/usr/bin/env python3
"""example: CLI for <SERVICE>. Built with the cli-able skill.

Template: rename NAME, set BASE_URL, replace the example commands (they wrap
the public GitHub API so the template runs as-is). Zero dependencies.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

NAME = "example"
ENV = NAME.upper().replace("-", "_")
BASE_URL = os.environ.get(f"{ENV}_BASE_URL", "https://api.github.com")
TOKEN = os.environ.get(f"{ENV}_TOKEN")
TIMEOUT = 30
RETRIES = 4


class ApiError(Exception):
    pass


def log(*args):
    print(*args, file=sys.stderr)


def request(method, path, params=None, data=None, dry_run=False):
    """Send one request; return (parsed body, headers). Retries 429/5xx and network errors."""
    url = path if path.startswith("http") else BASE_URL.rstrip("/") + "/" + path.lstrip("/")
    params = {k: v for k, v in (params or {}).items() if v is not None}
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    headers = {"User-Agent": f"{NAME}-cli/0.1", "Accept": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    if dry_run:  # headers left out on purpose: they hold the token
        print(json.dumps({"method": method, "url": url, "body": data}, indent=2))
        return None, {}

    for attempt in range(RETRIES + 1):
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                raw = resp.read().decode(resp.headers.get_content_charset() or "utf-8")
                is_json = "json" in resp.headers.get("Content-Type", "")
                return (json.loads(raw) if raw and is_json else raw or None), resp.headers
        except urllib.error.HTTPError as e:
            if (e.code == 429 or e.code >= 500) and attempt < RETRIES:
                try:
                    wait = float(e.headers.get("Retry-After"))
                except (TypeError, ValueError):  # missing, or an HTTP date
                    wait = 2 ** attempt
                wait = min(wait, 60)
                log(f"HTTP {e.code}, retrying in {wait:.0f}s")
                time.sleep(wait)
                continue
            detail = e.read().decode(errors="replace")[:500]
            raise ApiError(f"HTTP {e.code} {method} {url}: {detail}") from None
        except urllib.error.URLError as e:
            if attempt < RETRIES:
                time.sleep(2 ** attempt)
                continue
            raise ApiError(f"{method} {url}: {e.reason}") from None


def paginate(path, params=None, limit=None):
    """Yield items across pages. This follows a Link: rel="next" header;
    adapt for cursor fields (data.next_cursor) or offset/page params."""
    url, params, count = path, dict(params or {}, per_page=100), 0
    while url:
        page, headers = request("GET", url, params)
        for item in page:
            yield item
            count += 1
            if limit and count >= limit:
                return
        match = re.search(r'<([^>]+)>;\s*rel="next"', headers.get("Link", ""))
        url, params = (match.group(1) if match else None), None


def output(data, args, fields):
    """--json: raw JSON. Otherwise one tab-separated line per item with `fields`."""
    if args.json:
        print(json.dumps(data, indent=2))
        return
    for row in data if isinstance(data, list) else [data]:
        print("\t".join(str(row.get(f, "")) for f in fields) if isinstance(row, dict) else row)


def confirm(args, what):
    """Gate destructive actions: --yes, or an interactive y/N prompt."""
    if args.yes:
        return
    if not sys.stdin.isatty():
        sys.exit(f"{what}: refusing without --yes (stdin is not a terminal)")
    print(f"{what}? [y/N] ", end="", file=sys.stderr, flush=True)
    try:
        answer = input().strip().lower()
    except EOFError:  # Windows reports NUL as a tty
        answer = ""
    if answer != "y":
        sys.exit("aborted")


# --- commands: replace these with the user's jobs ---------------------------

def cmd_repos_list(args):
    items = list(paginate(f"/users/{args.user}/repos", {"sort": "updated"},
                          None if args.all else args.limit))
    output(items, args, ["full_name", "stargazers_count", "description"])


def cmd_repos_get(args):
    data, _ = request("GET", f"/repos/{args.repo}")
    output(data, args, ["full_name", "stargazers_count", "open_issues_count", "html_url"])


def cmd_api(args):
    method = args.method.upper()
    if method == "DELETE" and not args.dry_run:
        confirm(args, f"DELETE {args.path}")
    data, _ = request(method, args.path, data=json.loads(args.data) if args.data else None,
                      dry_run=args.dry_run)
    if not args.dry_run:
        print(json.dumps(data, indent=2) if not isinstance(data, str) else data)


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="print raw JSON to stdout")

    def leaf(sub, name, func, help, example):
        p = sub.add_parser(name, parents=[common], help=help, description=help,
                           epilog=f"example:\n  {example}",
                           formatter_class=argparse.RawDescriptionHelpFormatter)
        p.set_defaults(func=func)
        return p

    parser = argparse.ArgumentParser(
        prog=NAME, description=f"CLI for <SERVICE> ({BASE_URL})",
        epilog=f"env: {ENV}_TOKEN (auth), {ENV}_BASE_URL (override API root)")
    top = parser.add_subparsers(dest="cmd", required=True)

    repos = top.add_parser("repos", help="repositories").add_subparsers(dest="verb", required=True)
    p = leaf(repos, "list", cmd_repos_list, "list a user's repositories",
             f"{NAME} repos list octocat --limit 5")
    p.add_argument("user")
    p.add_argument("--limit", type=int, default=30, help="max items (default 30)")
    p.add_argument("--all", action="store_true", help="fetch every page")
    p = leaf(repos, "get", cmd_repos_get, "show one repository", f"{NAME} repos get octocat/Hello-World")
    p.add_argument("repo", help="OWNER/NAME")

    p = leaf(top, "api", cmd_api, "raw request against the API",
             f"{NAME} api GET /rate_limit")
    p.add_argument("method")
    p.add_argument("path")
    p.add_argument("--data", help="JSON request body")
    p.add_argument("--dry-run", action="store_true", help="print the request instead of sending it")
    p.add_argument("--yes", action="store_true", help="skip confirmation for destructive methods")
    return parser


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # pipes on Windows default to cp1252
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except ApiError as e:
        log(f"error: {e}")
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
