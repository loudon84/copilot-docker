# Runtime Deployment

Hermes multi-instance deployment mounts per-profile data directories and injects Expert Source components into `HERMES_HOME` for live use.

## Instance Lifecycle

Create/up/down/restart scripts allocate WebUI and Gateway ports and mount `instances/<profile>/data/hermes`.

Compose service `hermes-agent-webui` builds from the root Dockerfile with Hermes WebUI, Agent, optional GBrain, and healthchecks. Profile is selected via `HERMES_PROFILE`.

## Expert Injection

`inject-expert.sh` / `inject-expert-team.sh` copy Manifest-declared skills, policies, plugins, and entrypoints into an instance without shipping template secrets.

v1 Manifest drives precise component paths. Team experts inject root + member profiles. After inject, restart the instance to reload SOUL/skills.

## Asset Bundle vs Expert Bundle

Asset Bundles migrate runtime assets between instances; Expert Bundles are immutable registry-publishable expert packages.

Keep the two formats separate: Asset export/import scripts must not be confused with `expert build` Release artifacts. Promotion from mature instance back to template uses dedicated promote scripts, not Nacos publish.
