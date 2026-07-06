# Build History — Notification Manager HA Add-on

Digest of the Claude Code session(s) that built and debugged this add-on. Source transcript covered a debugging/fix pass on 2026-07-05/06 (the original scaffolding of `main.py`, `ha_client.py`, `config_manager.py`, templates, Dockerfile, `config.yaml`, and the CI workflow happened in an earlier, uncaptured session — this digest only covers what's evidenced).

---

## 1. What the add-on is and how it's structured

**Repo:** `github.com/traviswolverton/ha_user_control` — a Home Assistant **add-on repository** (contains a `repository.yaml` at root, standard for HA custom add-on repos).

`repository.yaml`:
```yaml
name: Travis's HA Add-ons
url: https://github.com/traviswolverton/ha_user_control
maintainer: Travis Wolverton <traviswolverton@gmail.com>
```

**Single add-on inside it:** `notification-manager/` — "Notification Manager" / sidebar title "Notify Manager". It's the management UI for the separate `script.notify_group` automation system documented at [`docs/ha-notifications.md`](docs/ha-notifications.md) (copied from the main homelab repo).

### File layout (`notification-manager/`)
```
notification-manager/
├── Dockerfile
├── config.yaml
└── app/
    ├── main.py             # FastAPI routes
    ├── ha_client.py        # talks to HA Core REST API via Supervisor token
    ├── config_manager.py   # reads/writes /config/configuration.yaml directly
    └── templates/
        ├── base.html       # Bootstrap 5.3.3 + bootstrap-icons 1.11.3, loaded from CDN
        └── index.html      # single-page UI with 4 tabs: Groups, Users, Opt-outs, Snooze
```
Plus at repo root: `.github/workflows/build.yml` (CI), `repository.yaml`, `README.md`.

### Stack
- **Language/framework:** Python 3.11, FastAPI 0.110.3 + Uvicorn 0.29.0 + Jinja2 3.1.4, `pyyaml`, `requests==2.31.0`, `python-multipart==0.0.9`.
- **Dockerfile:**
```dockerfile
FROM python:3.11-slim
RUN pip3 install --no-cache-dir \
    fastapi==0.110.3 uvicorn==0.29.0 jinja2==3.1.4 pyyaml \
    requests==2.31.0 python-multipart==0.0.9
COPY app/ /app/
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8099", "--app-dir", "/app"]
```
- **`config.yaml` (HA add-on manifest):**
```yaml
name: "Notification Manager"
description: "Manage notification groups, users, opt-outs, and snooze settings"
version: "1.0.1"
slug: "notification_manager"
init: false
arch: [amd64]
image: "ghcr.io/traviswolverton/ha_user_control/notification-manager"
homeassistant_api: true
ingress: true
ingress_port: 8099
ingress_entry: /
panel_icon: mdi:bell-cog
panel_title: Notify Manager
options: {}
schema: {}
map:
  - config:rw
```
- **Ports/access:** No externally exposed port — `ingress: true` means HA Supervisor proxies it through `/api/hassio_ingress/<per-session-token>/…`. Internally the container listens on **8099**. Access is via HA sidebar ("Notify Manager", bell-cog icon) or Settings → Add-ons → Notification Manager → Open Web UI.
- **`map: [config:rw]`** grants the container read/write access to HA's `/config` directory — needed because `config_manager.py` edits `/config/configuration.yaml` directly (`CONFIG_PATH = Path("/config/configuration.yaml")`).

### Routes (`app/main.py`)
- `GET /` — renders `index.html` with context: `groups`, `users`, `opt_outs`, `snooze` (all fetched live from HA via `ha_client.py`).
- `POST /groups/add` — creates a new notify group (adds `input_text.notify_group_<name>` + related helpers via `config_manager.add_group`, reloads `input_text`/`input_number`/`timer` domains, sets members, adds per-user opt-out booleans, reloads `input_boolean`).
- `POST /groups/{group}/members` — updates group membership.
- `POST /groups/{group}/delete` — deletes a group.
- `POST /users/add` — adds a new user.
- `POST /users/{user}/mute` — toggles master mute for a user.
- `POST /opt-outs/{user}/{group}` — toggles per-user/per-group opt-out boolean.
- `POST /snooze/{group}/start` / `/cancel` / `POST /snooze/{group}/duration` — snooze timer controls.

### `app/ha_client.py`
Thin wrapper around HA's REST API:
```python
_TOKEN = os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HA_TOKEN", "")
_BASE = (os.environ.get("HA_URL", "http://supervisor/core")) + "/api"
_HEADERS = {"Authorization": f"Bearer {_TOKEN}", "Content-Type": "application/json"}
```
Provides `call_service()`, `reload(*domains)`, and read helpers (`get_groups()` parses `input_text.notify_group_*` entity states). **`get_users()`, `get_opt_outs()`, `get_snooze()`, `set_group_members()` were referenced/used but not fully re-read in the last session** — pull these fresh from the repo before touching them.

### `app/config_manager.py`
Directly reads/writes `/config/configuration.yaml` via `yaml.safe_load`/`yaml.dump` (`default_flow_style=False, allow_unicode=True, sort_keys=False`). `add_group()` injects three keys into the config dict: `input_text.notify_group_<name>`, `input_number.<name>_snooze_duration` (min 5/max 480/step 5, initial 30, minutes), and `timer.<name>_snooze`. **`add_user_group_boolean()`'s body was cut off mid-read in the last session** (last seen: `config["input_boolean"][f"{username}_{group_name}_notifications"] = ...`) — re-read this file if working on user/group-boolean creation logic.

---

## 2. Architectural / design decisions and reasoning

- **Ingress instead of a published port** — deliberately embeds the app in the HA sidebar rather than exposing 8099 externally; keeps it inside HA's auth boundary and matches how other HA add-ons behave.
- **Pre-built ghcr.io image vs. Supervisor local build** — `config.yaml` references a pre-built `image:` field rather than letting Supervisor build from the local Dockerfile. This offloads the build to GitHub Actions (cross-compiled via QEMU/Buildx for `linux/amd64`) so the HAOS VM doesn't need to build it itself. This choice is exactly what caused Gotcha #1 below.
- **`X-Ingress-Path` header over relative-path hacks** — when fixing the ingress routing bug, relative-path hacks were explicitly rejected in favor of reading HA's officially-documented `X-Ingress-Path` header (injected by Supervisor on every proxied request) and using it to build a `base` prefix injected into template context and redirects — the officially supported way ingress add-ons should build their own base path.
- **Config editing strategy** — rather than trying to create `input_text`/`input_boolean`/etc. helpers via the API at runtime (not possible for YAML-defined helpers), the app edits `/config/configuration.yaml` directly and then calls `ha.reload(domain)` on the relevant helper domains (`input_text`, `input_number`, `timer`, `input_boolean`) so HA picks up new entities without a full restart. A `time.sleep(1)` is inserted between the config-write/reload and setting group members, presumably to let the reload complete before the newly-created `input_text` entity can be written to.
- **CI tag/version coupling** — originally the GitHub Actions workflow hardcoded image tags (`:latest`, `:1.0.0`) independent of `config.yaml`'s `version` field. This was redesigned to *derive* the pushed tag from `config.yaml`'s `version:` line (via a `grep`+`sed` step producing a `GITHUB_OUTPUT` value), so bumping the version always produces a matching, pullable image.

---

## 3. Bugs / gotchas encountered and fixed

### Gotcha 1: Supervisor caches by `version` field, not image content
- **Symptom:** Opening the add-on's Web UI returned `{"detail":"Not Found"}` — Starlette/FastAPI's literal default 404, meaning requests *were* reaching the FastAPI app, just hitting no matching route.
- **Root cause:** `config.yaml` used a pre-built `image:` reference. CI pushed to the same static tags (`:latest`, `:1.0.0`) on every push to `main`, but `config.yaml`'s `version: "1.0.0"` never changed. **HA Supervisor decides whether to re-pull an image by comparing the `version` string in `config.yaml`, not by checking if the tag's digest changed.** Supervisor was very likely still running whatever image existed at first install — an older `main.py` build without a working `/` route.
- **Fix:** Bump `version` in `notification-manager/config.yaml` on every meaningful change, push to `main`, then in HA go to the add-on page — it will show "Update available"; click Update to force a real re-pull.
- **Secondary fix (drift prevention):** CI hardcoded tag `:1.0.0`, so bumping `config.yaml`'s version alone would make Supervisor look for a tag CI never produced. Fixed by adding a "Read addon version" step to `.github/workflows/build.yml`:
  ```yaml
  - name: Read addon version
    id: version
    run: |
      VERSION=$(grep -m1 '^version:' notification-manager/config.yaml | sed -E 's/version: *"?([^"]+)"?/\1/')
      echo "value=$VERSION" >> "$GITHUB_OUTPUT"
  ```
  and referencing `${{ steps.version.outputs.value }}` in the `tags:` list of the build-push step instead of the literal `1.0.0`.

### Gotcha 2: Absolute paths break under ingress
- **Symptom:** Even once the index page loaded, submitting any form would "break out" of the HA panel.
- **Root cause:** Under ingress, the browser's actual location is `.../api/hassio_ingress/<token>/...`. Any absolute-path redirect (`RedirectResponse("/")`) or form `action="/groups/add"` navigates to HA's real root instead of staying inside the ingress proxy path.
- **Fix (`app/main.py`):** Added a `_base(request)` helper that reads `request.headers.get("X-Ingress-Path", "")`, added `base` to the Jinja context dict, and updated every POST handler's `RedirectResponse` to prefix with `_base(request)`.
- **Fix (`app/templates/index.html`):** All 9 form `action="/..."` attributes rewritten to `action="{{ base }}/..."`. Watch out if redoing this: a narrow regex missed paths containing Jinja `{{ }}` expressions with dots/special chars — use a broad pattern (`[^"]+`) to catch all forms in one pass. The 9 forms: `groups/{group}/delete`, `groups/{group}/members`, `groups/add`, `users/{user}/mute`, `users/add`, `opt-outs/{user}/{g}`, `snooze/{group}/duration`, `snooze/{group}/cancel`, `snooze/{group}/start`.

### Minor operational notes
- `gh` CLI is not installed on the Mac — fall back to `curl`/`WebFetch` against `raw.githubusercontent.com` and the GitHub REST contents API (`api.github.com/repos/.../contents/...`) to read repo files. `WebFetch` against the GitHub HTML tree view (`github.com/.../tree/main/...`) 404s — use raw file URLs or the REST API instead.

---

## 4. Deployment / install / build-publish flow

- **Custom add-on repo install (one-time):** HA → Settings → Add-ons → Add-on Store → ⋮ → Repositories → add `https://github.com/traviswolverton/ha_user_control`, then install "Notification Manager" and start it.
- **HA instance:** HAOS VM at `192.168.1.52:8123`.
- **Local network clone:** host `ubuntu-bride`, `192.168.1.67` per Ansible inventory (**this IP was inferred/corrected from an unconfirmed user typo of "195.168.1.67" — double check before relying on it**), path `/opt/ha_user_control`. Treat this clone as a checkout only — GitHub remains the single source of truth; make edits through GitHub, not locally on ubuntu-bride.
- **CI/CD (`.github/workflows/build.yml`):**
  - Trigger: push to `main` touching `notification-manager/**` or `.github/workflows/**`, or manual `workflow_dispatch`.
  - Steps: checkout → QEMU setup → Buildx setup → `docker/login-action` to `ghcr.io` (using `${{ github.actor }}` / `${{ secrets.GITHUB_TOKEN }}`) → read version from `config.yaml` → `docker/build-push-action@v5` building `notification-manager/` context for `linux/amd64`, pushing tags `ghcr.io/<repo>/notification-manager:latest` and `:<version-from-config.yaml>`, with GHA layer caching.
- **Update flow after a code change:**
  1. Edit files, bump `version` in `notification-manager/config.yaml`.
  2. Commit + push to `main` → Actions rebuilds and pushes the new ghcr.io tag automatically.
  3. In HA: Settings → Add-ons → Notification Manager shows "Update available" — click Update to force Supervisor to re-pull.
  4. Reopen the Web UI to verify.

---

## 5. Unresolved / open items

- **Unconfirmed:** whether `192.168.1.67` (vs. user's stated "195.168.1.67") is actually correct for the `ubuntu-bride` clone — worth double-checking against `ansible/inventory.yml` in the homelab repo before trusting it.
- **Unconfirmed:** whether the ingress-path fix was actually verified working end-to-end in production after the last push — the session ended right after pushing, with instructions to update in HA and reopen the Web UI, but no confirmation was captured.
- **Needs a fresh read before touching:** `ha_client.py`'s `get_users()`, `get_opt_outs()`, `get_snooze()`, `set_group_members()`, and `config_manager.py`'s `add_user_group_boolean()` — bodies weren't fully captured in the last session's transcript.

---

## 6. Secrets / credentials handling

- No secret values appear in the repo or its history.
- **Runtime auth to HA Core API:** `ha_client.py` reads `SUPERVISOR_TOKEN` (preferred) or `HA_TOKEN` from the environment. `SUPERVISOR_TOKEN` is auto-injected by HA Supervisor into add-on containers at runtime — no manual configuration needed. Base URL defaults to `http://supervisor/core` (overridable via `HA_URL`), matching `homeassistant_api: true` in `config.yaml`.
- **CI publish auth:** GitHub Actions logs into `ghcr.io` using `${{ github.actor }}` / `${{ secrets.GITHUB_TOKEN }}` — the automatic repo-scoped token, not a custom PAT.
- **Filesystem access:** `map: [config:rw]` in `config.yaml` gives the container write access to HA's `/config` directory (needed for `config_manager.py`) — a permission grant in the manifest, not a secret.
