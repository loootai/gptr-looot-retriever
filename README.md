# gptr-looot-retriever

A [GPT Researcher](https://github.com/assafelovic/gpt-researcher) retriever plugin that runs web search through [looot](https://looot.ai). looot is a pay-per-call API gateway for data endpoints. This plugin calls its `serper-search` endpoint (Google results) and hands the links to GPT Researcher, which scrapes them.

## Install for agents

```bash
pip install git+https://github.com/loootai/gptr-looot-retriever
claude mcp add --transport http looot https://api.looot.ai/mcp
```

See also: [awesome-looot-use-cases](https://github.com/loootai/awesome-looot-use-cases) (copy-paste recipes) and [awesome-gtm](https://github.com/loootai/awesome-gtm) (open-source GTM tools).

It follows GPT Researcher's [retriever plugin contract](https://github.com/assafelovic/gpt-researcher/blob/master/docs/docs/gpt-researcher/search-engines/retriever-plugins.md): the package registers `looot` in the `gpt_researcher.retrievers` entry-point group, so no change to GPT Researcher is needed.

## Install

```bash
pip install git+https://github.com/loootai/gptr-looot-retriever
```

Needs Python 3.12 or newer and `gpt-researcher>=0.16.1` (the first PyPI release with entry-point retriever plugins; it requires Python 3.12 itself).

## Use

```bash
export LOOOT_TOKEN=...        # from https://looot.ai
export RETRIEVER=looot
```

Combine it with built-in retrievers the usual way, for example `RETRIEVER=looot,arxiv`.

| Variable | Required | Meaning |
|---|---|---|
| `LOOOT_TOKEN` | yes | looot API token, sent as `Authorization: Bearer`. |
| `RETRIEVER` | yes | Set to `looot` (or a comma list that includes it). |
| `LOOOT_API_BASE` | no | Override the API base. Default `https://api.looot.ai`. |

## What it does

`search()` posts one run to `https://api.looot.ai/v1/runs?wait=30` with endpoint `serper-search`, input `{q, num}` and a fresh idempotency key. If the run is not finished after the 30 second wait, it polls `GET /v1/runs/{runId}` until the run reaches a terminal state or 60 seconds have passed. It maps `result.organic[]` to `[{"href": link, "body": snippet}]`.

When `query_domains` is set, the query gets ` site:a OR site:b` appended, the same as GPT Researcher's Serper retriever.

On a network error, an unparseable response, a missing result, or a run that ends `failed`, `blocked` or `stopped`, it logs a warning and returns `[]`, so one failing provider does not abort a research run.

## Price

$0.001 per call as of 2026-10-08 (from the [public catalog](https://api.looot.ai/v1/public-catalog?q=serper)). Failed calls are not charged. Top up from $5, no subscription. See [docs.looot.ai](https://docs.looot.ai).

## Tests

```bash
python3.13 -m venv .venv && . .venv/bin/activate
pip install -e '.[test]'
pytest
```

`tests/test_search.py` mocks the HTTP layer. `tests/test_plugin_registration.py` checks the installed entry point and that GPT Researcher's own `get_retriever("looot")` returns `LoootSearch`. Tests never call the live API.

## Licence

MIT. Copyright looot.
