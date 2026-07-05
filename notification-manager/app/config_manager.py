from pathlib import Path
import yaml

CONFIG_PATH = Path("/config/configuration.yaml")


def _load():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def _save(config):
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def add_group(group_name: str):
    """Add input_text, input_number, and timer entries for a new group."""
    config = _load()
    label = group_name.replace("_", " ").title()

    config["input_text"][f"notify_group_{group_name}"] = {
        "name": f"Notify Group – {label}",
        "initial": "",
        "icon": "mdi:account-group",
        "max": 255,
    }
    config["input_number"][f"{group_name}_snooze_duration"] = {
        "name": f"{label} Snooze Duration",
        "min": 5, "max": 480, "step": 5, "initial": 30,
        "unit_of_measurement": "minutes",
        "icon": "mdi:timer",
    }
    config["timer"][f"{group_name}_snooze"] = {
        "name": f"{label} Notifications Snoozed",
        "icon": "mdi:bell-sleep",
    }
    _save(config)


def add_user_group_boolean(username: str, group_name: str):
    """Add per-user per-group opt-out boolean."""
    config = _load()
    label_u = username.title()
    label_g = group_name.replace("_", " ").title()
    config["input_boolean"][f"{username}_{group_name}_notifications"] = {
        "name": f"{label_u} – {label_g} Notifications",
        "icon": "mdi:bell",
    }
    _save(config)


def add_user(username: str, device: str):
    """Add notification device (input_text) and master mute (input_boolean) for a new user."""
    config = _load()
    label = username.title()

    config["input_text"][f"{username}_notification_device"] = {
        "name": f"{label} Notification Device",
        "initial": device,
        "icon": "mdi:cellphone",
        "max": 255,
    }
    config["input_boolean"][f"{username}_notifications_muted"] = {
        "name": f"{label} – All Notifications Muted",
        "icon": "mdi:bell-off",
    }
    _save(config)


def remove_group(group_name: str):
    """Remove all helpers associated with a notification group."""
    config = _load()

    config["input_text"].pop(f"notify_group_{group_name}", None)
    config["input_number"].pop(f"{group_name}_snooze_duration", None)
    config["timer"].pop(f"{group_name}_snooze", None)

    to_remove = [k for k in config["input_boolean"] if k.endswith(f"_{group_name}_notifications")]
    for k in to_remove:
        del config["input_boolean"][k]

    _save(config)
