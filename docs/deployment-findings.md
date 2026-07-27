# AgentMemory — Fresh-workspace deployment findings (2026-07-27)

Deployed the accelerator to a clean workspace (`fevm-serverless-stable-agent-memo`,
catalog `serverless_stable_agent_memo_catalog`) from a fresh clone, as a non-expert
would. The happy path — `cp .env.example .env` (set 2 values) → `./scripts/deploy_bundle.sh dev`
→ run 3 notebooks — did NOT work end to end on first try. Eleven deploy/setup-blocking
bugs, all now fixed in this branch (`lm/bundle-create-schema`) and verified live on TWO
fresh workspaces (the second a full teardown → clean redeploy): the app comes up RUNNING
and backend-initialized from a single `deploy_bundle.sh` invocation. Ordered by where
they bite.

## Summary

| # | Symptom | Root cause | Fix | Severity |
|---|---------|-----------|-----|----------|
| 1 | Deploy aborts: "Cannot reach npm registry" | build_frontend.sh only falls back to prebuilt dist/ when npm is *absent*; with npm present but registry unreachable it hard-fails | Fall back to prebuilt dist/ on registry-unreachable too | High (blocks off-network users) |
| 2 | "Cannot deploy app … not in RUNNING state" | Script ran `apps deploy` on a freshly-created (STOPPED) app | Start app before deploy; move app deploy after grants | Blocker |
| 3 | "Source code path … is required for an app with no previous active deployment" | First `apps deploy` needs explicit `--source-code-path` | Pass resolved bundle source path | Blocker |
| 4 | App runs but API 503 "Lakebase not configured", missing all env | Inline `apps.config.command`/`.env` in databricks.yml is NOT delivered to the Apps runtime by CLI v1.3.0 — only resource bindings are | Generate `app.yaml` (command+env) from resolved ids at deploy | Blocker (app unusable) |
| 5 | Notebooks fail: "Databricks auth failed" | `ensure_databricks_auth` is env-driven, bails when DATABRICKS_HOST unset (always, in a notebook/job) | Fall back to ambient `WorkspaceClient()` SDK auth | Blocker (notebooks unrunnable) |
| 6 | Notebooks read wrong catalog | `.env.shared` gitignored + not in `sync.include`, never synced | Add `.env.shared` to `sync.include` | High |
| 7 | Notebooks fail: "cannot import name 'Vector' from pgvector.psycopg" | Serverless pgvector exposes `Vector` at top-level, not `.psycopg` | Import with fallback across both locations | Blocker |
| 8 | Seed/ingest fail: "Parent directory does not exist: /Shared/agent-memory" | `mlflow.set_experiment` won't create nested parent dirs; fresh workspace has none | `set_mlflow_experiment` helper mkdirs the parent first (used in all 5 call sites) | Blocker (ingest/eval/chat all trace) |
| 9 | 02_demo chat fails: "Lakebase not configured" (despite Lakebase working) | `databricks_configured` reads the frozen `Settings.databricks_host` (=None in a notebook); ambient auth sets the env only *after* freeze | Fall back to live env in `databricks_configured` | Blocker (chat/query path) |
| 10 | Clean deploy fails: "No command to run" (app has no command) | Generated `app.yaml` was gitignored but NOT in `sync.include`, so `bundle deploy` skipped it — the file never reached the workspace | Add `app.yaml` to `sync.include`; generate it *before* the first deploy too | Blocker (only shows on a truly fresh workspace) |
| 11 | Redeploy after teardown fails: 409 ALREADY_EXISTS on the app | Databricks Apps deletion is async; an immediate redeploy races the still-deleting app | Retry `bundle deploy` with backoff on ALREADY_EXISTS | Med (redeploy-after-destroy only) |
| — | Manual `CREATE SCHEMA` needed before deploy (prior session) | Schema not created by deploy | Create schema in deploy_bundle.sh + 00_setup (idempotent) | Med (already carried into this branch) |

## Detail + fixes

### Issue 1 — frontend build hard-fails instead of using shipped dist/
`scripts/build_frontend.sh` promised (INSTALL.md) "Node/npm is NOT required — the web
UI is pre-built." But the fallback to `dist/` only triggered when `npm` was *missing*.
On a machine WITH npm but no access to `https://npm-proxy.cloud.databricks.com/` (any
user off the Databricks network), the registry-reachability check did `exit 1` and
aborted the whole deploy (`set -e`), even though a perfectly good prebuilt UI was present.

**Fix:** when the registry is unreachable AND `frontend/dist/index.html` exists, warn
and use the prebuilt assets (`exit 0`) instead of failing.

### Issue 2 — app deployed before it was started
`bundle deploy` creates the Databricks App in a STOPPED state (no compute). The script
immediately ran `databricks apps deploy <name>`, which errors: *"Cannot deploy app … as
it is not in RUNNING state. Please start the app first."* Because the script uses
`set -e`, it aborted HERE — before running the UC schema creation, grants, and `.env`
write-back that come later in the file. So a first deploy left the app undeployed AND
the grants/schema unapplied.

**Fix:** (a) `databricks apps start <name>` (waits for ACTIVE) before deploying code;
(b) moved the app start+deploy to the END of the script, after schema/grants/.env, so a
slow or failed app step can't skip the critical UC setup.

### Issue 3 — first app deploy needs --source-code-path
Even with the app RUNNING, the first `databricks apps deploy <name>` fails: *"Source
code path or git source is required for an app with no previous active deployment."*
The API deploy path needs the workspace source path explicitly on the first deploy.

**Fix:** read the resolved app `source_code_path` from `bundle summary`
(`resources.apps.wealth_advisor.source_code_path`, fallback `workspace.file_path`) and
pass it via `--source-code-path`.

### Issue 4 — inline app config in databricks.yml never reaches the app (the big one)
The app started but every API call returned 503 *"Lakebase not configured…"*. Inspecting
the deployed app spec showed it had the Lakebase resource **binding** but **zero env
vars** and no command. Root cause: PR #6 ("single-source config") deleted the root
`app.yaml` and moved `command`/`env` into the bundle's inline `apps.<name>.config` in
databricks.yml — but that change was never deployed live (docs/progress.md literally
says "Not yet deployed live"). In CLI v1.3.0, the bundle delivers the app's resource
bindings but NOT the inline `config.command` / `config.env` to the Apps runtime. The
runtime reads `command`+`env` from an `app.yaml` in the deployed source, which no longer
existed → app came up with no command (build error) and, once a command was restored,
no env (503).

**Fix:** regenerate `app.yaml` (command + env) from the resolved bundle ids during
deploy — the same pattern already used to generate `.env.shared` for the notebooks.
`app.yaml` is gitignored and rebuilt every deploy with the workspace-specific warehouse
id + Lakebase endpoint, so nothing workspace-specific is committed. The bundle's inline
`config` is kept for the resource bindings (which DO work) but no longer relied on for
command/env.

**Alternative considered:** keep inline config and require a newer CLI that materializes
it. Rejected — pins users to newer/unreleased CLI behavior; generating app.yaml
works on the CLI users actually have and matches the repo's existing generate-from-.env
pattern.

### Issue 5 — setup notebooks fail auth in a serverless job/notebook
`00_setup` failed immediately: *"AssertionError: Databricks auth failed."* Probed the
serverless env: `DATABRICKS_HOST`/`DATABRICKS_TOKEN` are NOT set there, but a bare
`WorkspaceClient()` authenticates fine via the runtime's ambient credentials. Root cause:
`config.ensure_databricks_auth()` is env-driven — it returns False the moment
`settings.databricks_host` (from `os.getenv("DATABRICKS_HOST")`) is empty, so it never
reaches the SDK-default path. In a notebook/job (no `.env`), that's always empty → auth
always fails. This means the setup notebooks could not have run on a fresh deploy.

**Fix:** in `ensure_databricks_auth`, when no explicit host is configured, fall back to
the SDK default auth chain (`WorkspaceClient()`), adopt its resolved host + token, and
set `DATABRICKS_HOST`/`DATABRICKS_TOKEN` for the downstream LangChain/embeddings clients.
260 tests still pass.

### Issue 6 — generated notebook config (.env.shared) not synced to workspace
The notebooks read `UC_CATALOG`/`UC_SCHEMA`/FM endpoints from `.env.shared`
(`load_dotenv(f"{REPO_ROOT}/.env.shared")`). That file is generated by the deploy script
but is gitignored, and `bundle deploy` skips gitignored files unless they're in
`sync.include`. So it never reached the workspace, and `load_dotenv` silently no-op'd —
the notebooks would fall back to the wrong default catalog (`agent_memory`).

**Fix:** add `.env.shared` to `sync.include` in databricks.yml (same mechanism already
used for the gitignored `frontend/dist/**`). Confirmed it now lands in the workspace.

### Issue 7 — pgvector `Vector` import breaks on Databricks Serverless
`00_setup` (after auth was fixed) failed with *"ImportError: cannot import name 'Vector'
from 'pgvector.psycopg'"* in `store.py`. Probed serverless: its pgvector build exposes
`Vector` only at the TOP-LEVEL `pgvector` package, not `pgvector.psycopg` (which only has
lowercase `vector`/`register_vector`). Local dev pins a pgvector where `Vector` lives at
`pgvector.psycopg`. The pin (`pgvector>=0.3.0`) allows both, so the runtime resolved a
version the code didn't expect.

**Fix:** import with a fallback — `try: from pgvector.psycopg import Vector / except
ImportError: from pgvector import Vector`. Works on both. (`register_vector` in
connection.py is present in both versions, no change needed.)

### Issue 8 — MLflow experiment parent dir missing on fresh workspace
`01_seed` (ingest pipeline) failed: *"NOT_FOUND: Parent directory does not exist:
/Shared/agent-memory."* Every agent run sets the MLflow experiment to
`/Shared/agent-memory/<target>` (CLAUDE.md rule 7: trace on every run), but
`mlflow.set_experiment` does not create missing parent directories, and a fresh
workspace has no `/Shared/agent-memory`. Hit in 5 code paths (chat, streaming, ingest,
distillation, eval).

**Fix:** added `config.set_mlflow_experiment(settings)` — mkdirs the parent workspace
dir (recursive, idempotent, best-effort) before `mlflow.set_experiment`. Replaced all 5
inline `set_experiment` call sites with it.

### Issue 9 — frozen Settings makes the chat path think Lakebase is unconfigured
`02_demo` Panel 2 (semantic query) failed: *"Lakebase not configured…"* even though
00/01 had just used Lakebase successfully. `run.py` gates on `cfg.lakebase_configured`
→ `databricks_configured`, which reads the **frozen** `Settings.databricks_host`. In a
notebook that field is `None` at `Settings.from_env()` time (no `DATABRICKS_HOST` env);
`ensure_databricks_auth` then sets the env var, but the already-frozen dataclass still
holds `None`, so the gate reports "not configured." (00/01 dodged it — they open the
Lakebase connection directly and never hit this gate.)

**Fix:** `databricks_configured` now falls back to the live env
(`os.getenv("DATABRICKS_HOST"/"DATABRICKS_TOKEN")`) when the frozen fields are empty, so
the gate reflects the ambient credentials that auth just resolved.

### Issue 10 — generated app.yaml never synced to the workspace (found on a 2nd clean workspace)
Issue 4's fix generated `app.yaml` at deploy but gitignored it. On a genuinely fresh
workspace the app still failed with *"No command to run and no Python file found. Please
add a 'command' field to your app.yml file."* Root cause: `bundle deploy` skips
gitignored files unless they're in `sync.include` — and `app.yaml` was gitignored but
NOT listed there, so it never reached the workspace. (The first workspace only "passed"
because a hand-created `app.yaml` lingered from before it was gitignored; a second, truly
clean workspace exposed the gap.)

**Fix:** (a) add `app.yaml` to `sync.include` (same mechanism as `.env.shared` /
`frontend/dist/**`); (b) refactor generation into `write_app_yaml()` and call it *before*
the first `bundle deploy` too — the file must exist before its `sync.include` path is
read (the warehouse id + Lakebase host are filled in on a second call after
provisioning). Verified on a full teardown → clean redeploy: `app.yaml synced` → `App
code deployed` → app RUNNING.

### Issue 11 — teardown → immediate redeploy races the async app deletion
After `bundle destroy`, an immediate redeploy failed with *"Failed to create app
wealth-advisor-dev. An app with the same name already exists. (409 ALREADY_EXISTS)."*
Databricks Apps deletion is asynchronous: `destroy` returns before the app is fully
gone, so a fast redeploy collides with the still-deleting app. (First-time deploys are
unaffected; this only bites the destroy→redeploy cycle.)

**Fix:** wrap the first `bundle deploy` in a retry that backs off on `ALREADY_EXISTS`
(5 attempts, 20s×attempt) so a teardown→redeploy self-heals instead of erroring out.
Other errors still fail fast.

## Post-deploy (expected, not a bug)
Between deploy and `00_setup`, the app API returns 500 *"vector type not found in the
database"* — the Lakebase schema + `CREATE EXTENSION vector` are created by `00_setup`.
This is the documented next step (run 00_setup → 01_seed → 02_demo). Not a defect, but
see recommendation 2 to fold setup into the deploy.

## Recommendations toward one-step deploy
1. (Done) Fixes 1–11 above make `./scripts/deploy_bundle.sh dev` complete end-to-end and
   leave the app RUNNING + backend-initialized with correct config; verified on two fresh
   workspaces incl. a full teardown → clean redeploy.
2. (Done) `deploy_bundle.sh` now runs `00_setup` automatically at the end (serverless
   job submit + wait, `SKIP_SETUP=1` to opt out), so the app is immediately functional
   after one command — no notebook step required. `01_seed`/`02_demo` stay manual (they
   load demo data + walk the UI, which not every deployment wants).
3. Update docs/progress.md ADR-0016 note — the inline-config approach was never live and
   doesn't work on current CLI; app.yaml generation is the working design.
