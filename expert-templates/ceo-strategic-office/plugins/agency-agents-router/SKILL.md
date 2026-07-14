---
name: agency-agents-router
description: Search/view/load vendored Agency Agents and run them ephemerally via delegate_task.
---

# Agency Agents Router

## Commands

```bash
python plugins/agency-agents-router/router.py search "<query>"
python plugins/agency-agents-router/router.py view <agent_id>
python plugins/agency-agents-router/router.py load-prompt <agent_id>
```

## Isolation rules

- Ephemeral only — no permanent Profile identity
- Minimal task context — no credentials / unrestricted internal data
- No writes to `/data/hermes/team-shared` or other Profiles' memory
- On failure: return error to caller; caller may retry narrower, pick another agent, or continue with explicit missing-perspective disclosure
