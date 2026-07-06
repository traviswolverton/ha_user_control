# CLAUDE.md — ha_user_control

This directory manages the **Notification Manager** Home Assistant add-on.

- **GitHub repo:** `github.com/traviswolverton/ha_user_control` (this should be a clone of that repo — if this directory isn't a clone yet, `git clone` it here before making changes).
- **What it is:** a custom HA add-on (FastAPI + Jinja2, single add-on named `notification-manager/` inside an add-on repository) providing a web UI to manage the `script.notify_group` notification-routing system that lives in the separate `homelab` repo.
- **Read [`BUILD_HISTORY.md`](BUILD_HISTORY.md) before making changes** — it documents the file layout, architecture decisions, two non-obvious deployment gotchas (Supervisor version-caching, ingress path handling), the CI/build-publish flow, and known unread/unfinished code paths.
- **Read [`docs/ha-notifications.md`](docs/ha-notifications.md)** for the underlying `script.notify_group` automation system this add-on is a UI for (group/user/opt-out/snooze entity naming conventions this add-on's `config_manager.py` generates).

## Deployment quick reference

1. Edit `notification-manager/app/*` or `config.yaml`.
2. **Bump `version` in `notification-manager/config.yaml`** — HA Supervisor only re-pulls the image when this string changes, regardless of whether the underlying image tag content changed.
3. Commit + push to `main` → GitHub Actions (`.github/workflows/build.yml`) builds and pushes `ghcr.io/traviswolverton/ha_user_control/notification-manager` tagged `:latest` and `:<version>` (tag is derived from `config.yaml`, keep them in sync).
4. In HA (`192.168.1.52:8123`) → Settings → Add-ons → Notification Manager → Update → reopen Web UI to verify.

## Ingress gotcha

This add-on runs behind HA's per-session ingress proxy (`ingress: true`, no exposed port). Any redirect or form `action` must be prefixed with the `X-Ingress-Path` header value (see `_base()` in `app/main.py`) — absolute paths like `/` or `/groups/add` will escape the ingress proxy and 404 against HA's real root.

## Other known facts

- Local network clone (checkout only, not source of truth): host `ubuntu-bride`, `/opt/ha_user_control` — **the IP for this host is unconfirmed** (inferred as `192.168.1.67` from Ansible inventory during a past session; user originally typed "195.168.1.67" and never confirmed which is correct). Verify against `ansible/inventory.yml` in the homelab repo if it matters.
- `gh` CLI is not installed on the Mac this was built from — use `curl`/raw GitHub URLs / REST contents API instead of the GitHub HTML tree view (which 404s via fetch tools).
- No secrets in this repo. Runtime auth to HA Core API uses `SUPERVISOR_TOKEN`, auto-injected by Supervisor — nothing to configure manually.
