# Home Assistant Notification System

## Architecture

All notifications route through a single central script (`script.notify_group`) that resolves group membership, checks mute/snooze state, and sends to each user's device. Automations and scripts never call `notify.*` directly.

```
automation → script.notify_group(group, title, message, data?)
                 │
                 ├─ [bail if timer.<group>_snooze is active]
                 │
                 └─ for each user in input_text.notify_group_<group>:
                       ├─ [skip if input_boolean.<user>_notifications_muted = on]
                       ├─ [skip if input_boolean.<user>_<group>_notifications = off]
                       └─ notify.<user>_notification_device
```

### Three-layer opt-out

| Layer | Entity | Who controls it |
|---|---|---|
| Group snooze | `timer.<group>_snooze` | Anyone — timed, auto-expires |
| Master mute | `input_boolean.<user>_notifications_muted` | The user |
| Per-group opt-out | `input_boolean.<user>_<group>_notifications` | The user |

A missing per-group opt-out boolean is treated as **opted in** (fail open).

---

## Existing Groups

| Group | Members | Snooze timer |
|---|---|---|
| `frigate` | travis, libby | `timer.frigate_snooze` |
| `garage` | travis, libby | `timer.garage_snooze` |
| `front_door` | travis, libby | `timer.front_door_snooze` |
| `location` | travis, libby | `timer.location_snooze` |

---

## Naming Conventions

All entity IDs follow strict conventions — the central script constructs them dynamically, so deviating breaks routing silently.

| Purpose | Pattern | Example |
|---|---|---|
| Group member list | `input_text.notify_group_<group>` | `input_text.notify_group_frigate` |
| User device endpoint | `input_text.<user>_notification_device` | `input_text.travis_notification_device` |
| Master mute | `input_boolean.<user>_notifications_muted` | `input_boolean.libby_notifications_muted` |
| Per-group opt-out | `input_boolean.<user>_<group>_notifications` | `input_boolean.libby_frigate_notifications` |
| Snooze duration | `input_number.<group>_snooze_duration` | `input_number.frigate_snooze_duration` |
| Snooze timer | `timer.<group>_snooze` | `timer.frigate_snooze` |

---

## Adding a New Group

All steps are done in the HA UI — no YAML changes required.

**Settings → Devices & Services → Helpers → Add Helper**

### Step 1 — Group member list
- Type: **Text**
- Name: `notify_group_<group>` (e.g. `notify_group_plex`)
- Value: comma-separated usernames, e.g. `travis,libby`

### Step 2 — Snooze duration
- Type: **Number**
- Name: `<group>_snooze_duration` (e.g. `plex_snooze_duration`)
- Min: 5 / Max: 480 / Step: 5 / Unit: minutes
- Initial value: `30`

### Step 3 — Snooze timer
- Type: **Timer**
- Name: `<group>_snooze` (e.g. `plex_snooze`)
- Duration: leave at 0 (set at runtime by `script.snooze_group`)

### Step 4 — Per-user opt-out booleans (optional but recommended)
For each user in the group, create:
- Type: **Toggle**
- Name: `<user>_<group>_notifications` (e.g. `travis_plex_notifications`, `libby_plex_notifications`)
- Default: **on**

> If you skip this step, users are treated as opted-in. Create them when you want users to be able to self-manage.

### Step 5 — Use in an automation
```yaml
action: script.notify_group
data:
  group: plex
  title: "Plex"
  message: "Someone started watching something"
```

With rich data (attachments, actions):
```yaml
action: script.notify_group
data:
  group: frigate
  title: "Driveway – Person detected"
  message: "Person spotted (94% confidence)"
  data:
    attachment:
      url: "http://192.168.1.40:5000/api/events/{{ event_id }}/snapshot.jpg"
      content-type: jpeg
    push:
      sound:
        name: default
```

---

## Adding a New User

**Settings → Devices & Services → Helpers → Add Helper**

### Step 1 — Device endpoint
- Type: **Text**
- Name: `<user>_notification_device`
- Value: the `mobile_app_*` service name for their phone
  - Find it: Developer Tools → Services → search `notify` → look for `notify.mobile_app_*`

### Step 2 — Master mute
- Type: **Toggle**
- Name: `<user>_notifications_muted`
- Default: **off**

### Step 3 — Add to groups
Edit the relevant `input_text.notify_group_<group>` helpers to include the new username.

### Step 4 — Per-group opt-outs
Create `input_boolean.<user>_<group>_notifications` for each group they belong to (default on).

---

## Snoozing a Group

From an automation or dashboard button:

```yaml
action: script.snooze_group
data:
  group: frigate
```

This reads `input_number.frigate_snooze_duration` (minutes) and starts `timer.frigate_snooze`. When the timer expires, notifications resume automatically. To cancel early, call `timer.cancel` on the relevant timer.

To add a snooze button to a dashboard card:
```yaml
type: button
name: Snooze Frigate (30 min)
tap_action:
  action: call-service
  service: script.snooze_group
  data:
    group: frigate
```

---

## Deprecated Helpers (can be removed)

These helpers were used by the old per-flow notification system and are no longer referenced:

- `input_text.garage_notification_users`
- `input_text.front_door_notification_users`
- `input_text.frigate_notification_users`
- `input_text.frigate_device_map`
- `input_text.travis_notification_device` ← keep, still used
- `input_text.libby_notification_device` ← keep, still used
- `input_text.seth_notification_device` ← keep, used by Seth's NFC tag automation
- `input_text.caroline_notification_device` ← keep, used by Caroline's NFC tag automation
