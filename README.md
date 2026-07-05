# ha_user_control

Home Assistant add-on repository (`repository.yaml`) containing one add-on: **Notification Manager** (`notification-manager/`).

## What it does

A small FastAPI app, embedded in the HA sidebar via Ingress, for managing the
central notification system documented in the main homelab repo at
`docs/ha-notifications.md` (`/Volumes/homelab_docs/homelab/docs/ha-notifications.md`).
It lets you add/remove notification groups and users, toggle mute/opt-out
booleans, and start/cancel snooze timers — all without touching YAML by hand.

It reads/writes HA state via the Supervisor-injected `SUPERVISOR_TOKEN`
(`app/ha_client.py`, calls `http://supervisor/core/api/...`) and edits
`/config/configuration.yaml` directly for helper definitions (`app/config_manager.py`).
The addon's `config.yaml` maps `config:rw` so it can write to `/config`.

## Deployment

- **Source of truth / where to edit:** this GitHub repo, not the running container.
- **Local clone on the network:** `192.168.1.67` (host `ubuntu-bride` in the
  homelab Ansible inventory), path `/opt/ha_user_control`. Edits should still
  go through GitHub — treat the local clone as a checkout, not a second source
  of truth.
- **Install target:** HAOS VM at `192.168.1.52` (`http://192.168.1.52:8123`),
  installed as a custom add-on repository pointing at this GitHub URL.
- **Build/publish:** `.github/workflows/build.yml` builds `notification-manager/`
  on every push to `main` and pushes to
  `ghcr.io/traviswolverton/ha_user_control/notification-manager` as both
  `:latest` and `:<version>`, where `<version>` is read directly from
  `notification-manager/config.yaml`'s `version:` field (not hardcoded).

## Critical gotcha: bump `version` on every change

`notification-manager/config.yaml` uses a pre-built `image:` reference rather
than telling Supervisor to build from the local Dockerfile. **Supervisor only
re-pulls the image when the `version` field changes** — it does not detect
that a tag's contents changed upstream. If you push code without bumping
`version`, HA will keep running the old container and the change will appear
to silently not exist (this exact symptom — a stale build serving a 404 for
routes that clearly exist in `main.py` — is what prompted this note).

**Every change to `notification-manager/` must include a `version` bump in
`config.yaml`.** After pushing, in HA go to Settings → Add-ons → Notification
Manager and click Update (an "Update available" banner should appear once CI
finishes).

## Critical gotcha: HA Ingress path prefix

The app is served behind Supervisor's ingress proxy at a per-session URL like
`/api/hassio_ingress/<token>/`, not at the domain root. Any **absolute** path
(`"/"`, `"/groups/add"`, etc.) in a redirect or form `action` resolves against
the real HA root and 404s instead of routing back into the app.

The fix in place: `main.py` has a `_base(request)` helper that reads the
`X-Ingress-Path` request header (set by Supervisor on every proxied request)
and all `RedirectResponse` calls prefix with it. `templates/index.html` passes
`base` into the template context and every `<form action="...">` is prefixed
with `{{ base }}`. **Any new route, redirect, or form added to this app must
follow the same pattern** — never hardcode a leading `/` path in a redirect or
form action.

## Repo layout

```
repository.yaml                          # HA add-on repo manifest
notification-manager/
  config.yaml                            # HA add-on manifest (version, ingress port 8099, image ref)
  Dockerfile                             # python:3.11-slim, uvicorn on :8099
  app/
    main.py                              # FastAPI routes
    ha_client.py                         # HA REST API calls via SUPERVISOR_TOKEN
    config_manager.py                    # direct edits to /config/configuration.yaml
    templates/
      base.html
      index.html
.github/workflows/build.yml              # builds+pushes image on push to main
```
