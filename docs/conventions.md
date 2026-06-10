# Conventions

## Python

- Python 3.10+ (floor is 3.10 to match Databricks Serverless; don't use 3.11-only APIs like `datetime.UTC` — use `timezone.utc`)
- Formatter + linter: **ruff** (config in `pyproject.toml`)
- Type-checker: **pyright** (strict for `src/agent_memory/`, basic for `tests/`)
- Tests: **pytest** — every new module gets at least a smoke test
- Imports: sorted by ruff; no relative imports beyond one level
- Docstrings: every public function has one; explain *why*, not *what*
- No comments that narrate the code or reference tickets ("// for the May 12 review") — that lives in commits and PRs

## Project layout

- Application code goes under `src/agent_memory/` — never in repo root
- Notebooks are the **non-expert deploy + demo path** and are for humans reading them. They orchestrate setup (provision, seed) and walk a customer through the accelerator. Don't `import` from notebooks; anything reusable graduates to `src/`
- Synthetic data lives in `data/synthetic/`. The generator is checked in, the *output* is gitignored
- Real PII never enters the repo. Ever.
- **Legibility bar:** a new SA without deep platform expertise should be able to follow the structure and deploy via `databricks bundle deploy` + the setup notebooks. Keep the happy path short and the module layout obvious.

## Commits & branches

- Branch from `main` as `<initials>/<short-topic>` — e.g. `me/lakebase-schema`
- One logical change per commit. Commit messages explain *why*.
- Squash-merge PRs; PR title is the squashed commit message
- Never push to `main`
- Never `--force` push to a shared branch

## Pull requests

- Use the template in `.github/PULL_REQUEST_TEMPLATE.md`
- Link the milestone or task ID from `docs/progress.md`
- If you added a dependency or made a stack-level choice, add an ADR to `docs/decisions.md` in the same PR
- CI must be green before merge
- One human reviewer minimum (or co-owner on agent-only PRs)

## When to update `docs/`

| You did this | Update |
|---|---|
| Started a task | `progress.md` — move to "in progress" |
| Finished a task | `progress.md` — move to "Done" |
| Made a non-trivial design choice | `decisions.md` — new ADR |
| Added a new domain term | `glossary.md` |
| Changed the stack | `CLAUDE.md` + `architecture.md` + new ADR |
| Added a new functional requirement | `requirements.md` |

## Working with AI assistants

This repo is set up for context-engineering. The expected workflow:

1. AI assistant reads `CLAUDE.md` → routes to relevant `docs/` file
2. For new tasks, pull from `docs/progress.md` open-task list
3. Update progress.md on start and finish
4. Add ADRs for decisions; don't make them silently in code

If an AI assistant tries to add a non-Databricks memory service, reject the PR. See CLAUDE.md house rules.
