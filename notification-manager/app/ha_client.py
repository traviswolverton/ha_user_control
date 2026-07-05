import os
import requests

_TOKEN = os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HA_TOKEN", "")
_BASE = (os.environ.get("HA_URL", "http://supervisor/core")) + "/api"
_HEADERS = {"Authorization": f"Bearer {_TOKEN}", "Content-Type": "application/json"}


def _get(path: str):
    r = requests.get(f"{_BASE}/{path}", headers=_HEADERS, timeout=10)
    r.raise_for_status()
    return r.json()


def _post(path: str, data: dict | None = None):
    r = requests.post(f"{_BASE}/{path}", headers=_HEADERS, json=data or {}, timeout=10)
    r.raise_for_status()
    return r.json()


def _state(entity_id: str) -> dict | None:
    try:
        return _get(f"states/{entity_id}")
    except Exception:
        return None


def _states() -> list[dict]:
    return _get("states")


def call_service(domain: str, service: str, data: dict | None = None):
    return _post(f"services/{domain}/{service}", data)


def reload(*domains: str):
    for d in domains:
        call_service(d, "reload")


# ── Read helpers ──────────────────────────────────────────────────────────────

def get_groups() -> dict[str, list[str]]:
    """group_name -> sorted member list"""
    groups = {}
    for s in _states():
        eid = s["entity_id"]
        if eid.startswith("input_text.notify_group_"):
            name = eid[len("input_text.notify_group_"):]
            val = s.get("state", "")
            members = sorted(m.strip() for m in val.split(",") if m.strip())
            groups[name] = members
    return dict(sorted(groups.items()))


def get_users() -> dict[str, str]:
    """username -> device service name"""
    users = {}
    for s in _states():
        eid = s["entity_id"]
        if (eid.startswith("input_text.")
                and eid.endswith("_notification_device")
                and not eid.startswith("input_text.notify_group_")):
            user = eid[len("input_text."):-len("_notification_device")]
            users[user] = s.get("state", "")
    return dict(sorted(users.items()))


def get_snooze(group_names: list[str]) -> dict:
    """group -> {active, duration, remaining}"""
    result = {}
    for name in group_names:
        timer = _state(f"timer.{name}_snooze")
        dur_state = _state(f"input_number.{name}_snooze_duration")
        duration = int(float(dur_state["state"])) if dur_state else 30
        active = timer and timer.get("state") == "active"
        remaining = timer["attributes"].get("remaining") if active and timer else None
        result[name] = {"active": active, "duration": duration, "remaining": remaining}
    return result


def get_opt_outs(group_names: list[str], user_names: list[str]) -> dict:
    """user -> {_muted: bool, group_name: bool (True=opted-in)}"""
    result = {}
    for user in user_names:
        mute = _state(f"input_boolean.{user}_notifications_muted")
        row = {"_muted": mute["state"] == "on" if mute else False}
        for group in group_names:
            s = _state(f"input_boolean.{user}_{group}_notifications")
            row[group] = s["state"] == "on" if s else True  # missing = opted in
        result[user] = row
    return result


# ── Write helpers ─────────────────────────────────────────────────────────────

def set_group_members(group: str, members: list[str]):
    call_service("input_text", "set_value", {
        "entity_id": f"input_text.notify_group_{group}",
        "value": ",".join(members),
    })


def set_opt_out(user: str, group: str, enabled: bool):
    svc = "turn_on" if enabled else "turn_off"
    call_service("input_boolean", svc, {
        "entity_id": f"input_boolean.{user}_{group}_notifications"
    })


def set_muted(user: str, muted: bool):
    svc = "turn_on" if muted else "turn_off"
    call_service("input_boolean", svc, {
        "entity_id": f"input_boolean.{user}_notifications_muted"
    })


def start_snooze(group: str):
    dur = _state(f"input_number.{group}_snooze_duration")
    secs = int(float(dur["state"])) * 60 if dur else 1800
    call_service("timer", "start", {"entity_id": f"timer.{group}_snooze", "duration": secs})


def cancel_snooze(group: str):
    call_service("timer", "cancel", {"entity_id": f"timer.{group}_snooze"})


def set_snooze_duration(group: str, minutes: int):
    call_service("input_number", "set_value", {
        "entity_id": f"input_number.{group}_snooze_duration",
        "value": minutes,
    })
