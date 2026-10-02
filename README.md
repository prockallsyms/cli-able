# cli-able

cli-able is an LLM agent skill that converts any website or API that you have access to into a CLI tool.

Point your agent at an API, an OpenAPI spec, or a plain website, and tell it what you want to do there. The skill walks it through:

1. Finding the most stable interface. It checks for an official CLI, an OpenAPI or GraphQL schema, API docs, the site's own JSON backend, and only then falls back to HTML scraping.
2. Testing real requests before it writes any code.
3. Generating a single-file, zero-dependency CLI with `--json` output, pagination, retries, env-var auth, `--dry-run`, and a raw `api` escape hatch.
4. Running the CLI against the live service before reporting done, then putting it on your PATH.
5. Optionally writing an agent skill for the new CLI, so your agents know how to use it.

## Install

### Any agent (Claude Code, Codex, Cursor, Pi, OpenCode, and 70+ others)

```sh
npx skills add prockallsyms/cli-able
```

This uses the [`skills`](https://github.com/vercel-labs/skills) installer. It detects your agents and asks where to install. Useful flags: `-g` installs globally, `-a codex` (or `-a claude-code`, `-a cursor`, `-a pi`) targets one agent, and `-y` skips the prompts.

### Claude Code plugin marketplace

```
/plugin marketplace add prockallsyms/cli-able
/plugin install cli-able@cli-able
```

## Use

Ask your agent:

> Make me a CLI for the Hacker News API that lists top stories and shows comments.

> Turn my company's internal dashboard at https://dash.example.com into a CLI. Here's a cURL copied from DevTools: ...

In Claude Code you can also invoke it directly with `/cli-able:cli-able`.

## Layout

```
.claude-plugin/marketplace.json   Claude Code marketplace (lists this repo as the plugin)
.claude-plugin/plugin.json        Claude Code plugin manifest
skills/cli-able/SKILL.md          the skill (Agent Skills format, read by every agent)
skills/cli-able/template.py       starter CLI the skill builds from
```

To check the template, run `python skills/cli-able/template.py repos list octocat`. It wraps the public GitHub API as a working example.
