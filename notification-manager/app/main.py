import time
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import ha_client as ha
import config_manager as cm

app = FastAPI()
templates = Jinja2Templates(directory="/app/templates")


def _ctx(request: Request) -> dict:
    groups = ha.get_groups()
    users = ha.get_users()
    return {
        "request": request,
        "groups": groups,
        "users": users,
        "opt_outs": ha.get_opt_outs(list(groups), list(users)),
        "snooze": ha.get_snooze(list(groups)),
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", _ctx(request))


# ── Groups ────────────────────────────────────────────────────────────────────

@app.post("/groups/add")
async def add_group(name: str = Form(...), members: str = Form(...)):
    member_list = [m.strip() for m in members.split(",") if m.strip()]
    cm.add_group(name)
    ha.reload("input_text", "input_number", "timer")
    time.sleep(1)
    ha.set_group_members(name, member_list)
    for user in ha.get_users():
        cm.add_user_group_boolean(user, name)
    ha.reload("input_boolean")
    return RedirectResponse("/", status_code=303)


@app.post("/groups/{group}/members")
async def update_members(group: str, members: str = Form(...)):
    member_list = [m.strip() for m in members.split(",") if m.strip()]
    ha.set_group_members(group, member_list)
    return RedirectResponse("/", status_code=303)


@app.post("/groups/{group}/delete")
async def delete_group(group: str):
    cm.remove_group(group)
    ha.reload("input_text", "input_number", "timer", "input_boolean")
    return RedirectResponse("/", status_code=303)


# ── Users ─────────────────────────────────────────────────────────────────────

@app.post("/users/add")
async def add_user(username: str = Form(...), device: str = Form(...)):
    cm.add_user(username, device)
    ha.reload("input_text", "input_boolean")
    time.sleep(1)
    for group in ha.get_groups():
        cm.add_user_group_boolean(username, group)
    ha.reload("input_boolean")
    return RedirectResponse("/", status_code=303)


@app.post("/users/{user}/mute")
async def toggle_mute(user: str, muted: str = Form(...)):
    ha.set_muted(user, muted == "true")
    return RedirectResponse("/", status_code=303)


# ── Opt-outs ──────────────────────────────────────────────────────────────────

@app.post("/opt-outs/{user}/{group}")
async def toggle_opt_out(user: str, group: str, enabled: str = Form(...)):
    ha.set_opt_out(user, group, enabled == "true")
    return RedirectResponse("/", status_code=303)


# ── Snooze ────────────────────────────────────────────────────────────────────

@app.post("/snooze/{group}/start")
async def start_snooze(group: str):
    ha.start_snooze(group)
    return RedirectResponse("/", status_code=303)


@app.post("/snooze/{group}/cancel")
async def cancel_snooze(group: str):
    ha.cancel_snooze(group)
    return RedirectResponse("/", status_code=303)


@app.post("/snooze/{group}/duration")
async def set_duration(group: str, minutes: int = Form(...)):
    ha.set_snooze_duration(group, minutes)
    return RedirectResponse("/", status_code=303)
