import hashlib
import json
import os
import sys
import traceback

from decouple import config
from pathlib import Path
from subprocess import check_output
from subprocess import run as bashrun

try:
    print("Default var for upstream repo & branch will used if none were given!")
    ALWAYS_DEPLOY_LATEST = config(
        "ALWAYS_DEPLOY_LATEST",
        default=False,
        cast=bool)
    AUPR = config("ALWAYS_UPDATE_PY_REQ", default=False, cast=bool)
    UPSTREAM_REPO = config(
        "UPSTREAM_REPO",
        default="https://github.com/Pah-0/neon_bot")
    UPSTREAM_BRANCH = config("UPSTREAM_BRANCH", default="main")

except Exception:
    print("Environment vars Missing")
    traceback.print_exc()


update_check = Path("update")
# Set by .update -pr: {"pr": number, "msg": "chat:id:server"}, plus "sha" once
# switched. While it exists, updates fetch the PR instead of UPSTREAM_BRANCH.
pr_state_file = Path(".pr_test")
# What happened to a PR test, for the bot to report on its next start
pr_result_file = Path(".pr_result")
# The bot's stderr while testing a PR (written by run.sh)
crash_log = Path(".bot_stderr.log")

cmd = (
    f"git switch {UPSTREAM_BRANCH} -q \
    && git pull -q "
    "&& git reset --hard @{u} -q \
    && git clean -df -q"
)
cmd2 = f"git init -q \
       && git config --global user.email 117080364+Niffy-the-conqueror@users.noreply.github.com \
       && git config --global user.name Niffy-the-conqueror \
       && git add . \
       && git commit -sm update -q \
       && git remote add origin {UPSTREAM_REPO} \
       && git fetch origin -q \
       && git reset --hard origin/{UPSTREAM_BRANCH} -q \
       && git switch {UPSTREAM_BRANCH} -q"


def read_json(path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def requirements_hash():
    try:
        return hashlib.sha256(
            Path("requirements.txt").read_bytes()).hexdigest()
    except OSError:
        return None


def has_upstream_repo():
    return os.path.exists(".git") and check_output(
        ["git config --get remote.origin.url"],
        shell=True).decode().strip() == UPSTREAM_REPO


def update_to_upstream():
    if UPSTREAM_BRANCH == "main":
        bashrun(["rm -rf .git"], shell=True)
    if has_upstream_repo():
        return bashrun([cmd], shell=True)
    return bashrun([cmd2], shell=True)


def update_to_pr(pr):
    # A repo is needed to fetch into; cmd2 makes one at UPSTREAM_BRANCH
    if not has_upstream_repo():
        bashrun(["rm -rf .git"], shell=True)
        if bashrun([cmd2], shell=True).returncode != 0:
            return False
    fetch = bashrun(
        [f"git fetch -q origin pull/{pr}/head && git reset --hard -q FETCH_HEAD"],
        shell=True)
    return fetch.returncode == 0


def short_sha():
    try:
        return check_output(
            ["git rev-parse --short HEAD"], shell=True).decode().strip()
    except Exception:
        return ""


def end_pr_test(state, reason, log=""):
    """Back to UPSTREAM_BRANCH, leaving a note for the bot to report."""
    pr_state_file.unlink(missing_ok=True)
    update = update_to_upstream()
    # Written after, as updating can remove untracked files
    pr_result_file.write_text(json.dumps(
        {"pr": state.get("pr"), "msg": state.get("msg"), "reason": reason,
         "log": log}))
    return update


try:
    # Read before git runs: resets and cleans can remove untracked files
    pr_state = read_json(pr_state_file)
    old_requirements = requirements_hash()
    revert = len(sys.argv) > 1 and sys.argv[1] == "--revert"
    update = None
    switched = False
    if revert and pr_state:
        # run.sh saw the bot crash while testing a PR
        code = sys.argv[2] if len(sys.argv) > 2 else "?"
        try:
            log = "\n".join(crash_log.read_text(
                errors="replace").splitlines()[-15:])
        except OSError:
            log = ""
        update = end_pr_test(pr_state, f"crashed (exit code {code})", log)
        print(
            f"PR #{
                pr_state.get('pr')} crashed, went back to {UPSTREAM_BRANCH}")
    elif pr_state and (ALWAYS_DEPLOY_LATEST is True or update_check.is_file()):
        if update_to_pr(pr_state["pr"]):
            pr_state["sha"] = short_sha()
            pr_state_file.write_text(json.dumps(pr_state))
            switched = True
            print(f"Switched to PR #{pr_state['pr']} ({pr_state['sha']})")
        else:
            update = end_pr_test(pr_state, "couldn't be fetched")
            print(f"Couldn't fetch PR #{pr_state['pr']}, updating as usual")
    elif ALWAYS_DEPLOY_LATEST is True or update_check.is_file():
        update = update_to_upstream()
    else:
        print("Auto-update is disabled.")

    if update is not None:
        if update.returncode == 0:
            print('Successfully updated with latest commit from UPSTREAM_REPO')
        else:
            print('Something went wrong while updating,maybe invalid upstream repo?')
    # A PR (or going back from one) can change the requirements
    if (update is not None or switched) and (
        AUPR or (pr_state and requirements_hash() != old_requirements)
    ):
        bashrun(["pip3", "install", "-r", "requirements.txt"])
    if update_check.is_file():
        os.remove("update")
except Exception:
    traceback.print_exc()
