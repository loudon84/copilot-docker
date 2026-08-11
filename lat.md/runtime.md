# Runtime Deployment

Hermes multi-instance deployment mounts per-profile data directories and injects Expert Source components into `HERMES_HOME` for live use.

## Instance Lifecycle

Create/up/down/restart scripts allocate WebUI and Gateway ports and mount `instances/<profile>/data/hermes`.

Compose service `hermes-agent-webui` builds from the root Dockerfile with Hermes WebUI, Agent, optional GBrain, and healthchecks. Profile is selected via `HERMES_PROFILE`. Capability cloning onto a **new** profile uses [[runtime#Runtime Deployment#Instance Capability Clone]].

## Expert Injection

`inject-expert.sh` / `inject-expert-team.sh` copy Manifest-declared skills, policies, plugins, and entrypoints into an instance without shipping template secrets.

v1 Manifest drives precise component paths. Team experts inject root + member profiles. After inject, restart the instance to reload SOUL/skills.

## Instance Capability Clone

Create-only cloning copies Hermes capability (configs, skills, tools) from instance A into a brand-new B without sessions or memories.

Entry: `scripts/clone-instance.sh`. Flow: export allowlisted capability → `create-instance.sh` skeleton for B → merge non-identity `.env` → apply bundle → seed empty memories → clear runtime history → rebind Hindsight banks → `sync-runtime-env.sh` → write `.instance-clone.json`.

Helpers: [[scripts/lib/clone_capability.py#export_bundle]], [[scripts/lib/clone_capability.py#apply_bundle]], [[scripts/lib/clone_env.py#rewrite_target]], [[scripts/lib/rebind_clone_runtime.py#rebind_config]]. Operator doc: `docs/instance-capability-clone.md`. Invariants: [[decisions#Design Decisions#Create-Only Instance Capability Clone]].

Preflight refuses an existing `instances/<target>`, an existing `hermes-<target>` container, colliding WebUI/gateway ports from other `.env` files, or a live `instances/.locks/clone-<target>.lock`. `--dry-run` exports and inspects the capability archive only; it never creates B.

### Capability Bundle Allowlist

The clone archive is an allowlisted capability payload, not a full Hermes home copy.

[[scripts/lib/clone_capability.py#export_bundle]] packs root/profile `config.yaml`, `SOUL.md`, `team.yaml`, `profile.yaml`, `config.patch.yaml`, skills/tools/plugins/mcp/policies/skill-bundles/cron/agent-hooks/team-shared, and `workspace/AGENTS.md` only. [[scripts/lib/clone_capability.py#validate_member]] rejects symlinks, path escape, and root/profile runtime trees (`sessions`, `memories`, `logs`, `webui`, `hindsight`, backups/attachments, `finance-bi`, `sqlbot-adapter`, workspace documents beyond `AGENTS.md`).

### Target Env Identity Merge

B must keep its own instance identity even when runtime switches are copied from A.

[[scripts/lib/clone_env.py#rewrite_target]] never overwrites `HERMES_PROFILE`, WebUI/gateway ports, WebUI password, `API_SERVER_KEY`, `API_SERVER_MODEL_NAME`, or `HINDSIGHT_BANK_ID`. Secret-like keys match `API_KEY`/`TOKEN`/`PASSWORD`/`SECRET`/`CREDENTIAL`/`PRIVATE_KEY` patterns and copy only with `--copy-secrets`. After merge, `sync-runtime-env.sh` refreshes `data/hermes/.env`.

### Hindsight Namespace Rebind

Cloned configs must not keep A's external Hindsight bank identifiers.

[[scripts/lib/rebind_clone_runtime.py#rebind_config]] forces root `memory.bank_id` to `hermes-<B>` and member profiles to `hermes-<B>-<profile>`, rewrites `hermes-<A>` tokens in YAML/`team.yaml`, then `--verify-only` fails if any source namespace remains. Empty local `memories/` and wiped `hindsight/` ensure B starts without A's conversation or local memory state.

## Asset Bundle vs Expert Bundle

Asset Bundles migrate runtime assets between instances; Expert Bundles are immutable registry-publishable expert packages.

Keep three flows separate: Asset export/import may merge into an **existing** instance; Instance Clone ([[runtime#Runtime Deployment#Instance Capability Clone]]) is create-only onto a missing target; `expert build` Release artifacts go to Nacos. Promotion from mature instance back to template uses dedicated promote scripts, not Nacos publish.
