import asyncio
import time

from bot import jid
from bot.config import bot, conf
from bot.utils.bot_utils import split_text
from bot.utils.db_utils import save2db2
from bot.utils.log_utils import logger
from bot.utils.msg_utils import (
    chat_is_allowed,
    clean_reply,
    find_role_mentions,
    get_args,
    get_mentioned,
    tag_all_users_in_role,
    user_is_admin,
    user_is_allowed,
    user_is_owner,
    user_is_privileged,
)

blocked_char = ('"', "'", " ", ".")
blocked_roles = ("admin", "mod", "owner", "sudoer")
blocked_roles2 = ("all", "everyone")
role_action_msg = "{0} role with name: *{1}* successfully!"

# Admins, owner and sudoers are exempt from both limits
TAG_COOLDOWN = 60  # seconds between tags of the same role in a group
MAX_ROLES_PER_USER = 10  # roles a user can create per group
last_tagged: dict[tuple[str, str], float] = {}


class Group:
    """Fetches a group's info at most once per event"""

    def __init__(self, event, client):
        self.event = event
        self.client = client
        self._info = None

    async def info(self):
        if self._info is None:
            self._info = await self.client.get_group_info(self.event.chat.jid)
        return self._info

    async def is_admin(self, user: str) -> bool:
        return bool(user_is_admin(user, (await self.info()).Participants))

    async def lid_map(self) -> dict[str, str]:
        """Every id a current participant is known by (LID, phone number) -> their LID"""
        ids = {}
        for p in (await self.info()).Participants:
            lid = p.JID.User if p.JID.Server == "lid" else p.LID.User
            if not lid:
                continue
            for user in (p.JID.User, p.LID.User, p.PhoneNumber.User):
                if user:
                    ids[user] = lid
        return ids


def current_members(members: list, ids: dict[str, str]) -> list:
    # Converts to LIDs and drops users who left the group, keeping order
    return list(dict.fromkeys(ids[m] for m in members if m in ids))


async def get_roles(event, group: Group) -> dict:
    """
    Returns the chat's roles, first converting roles made before the group
    moved to LIDs; members who left the group are dropped.
    """
    gc_roles = bot.group_dict.setdefault(event.chat.id, {}).setdefault("roles", {})
    legacy = [role for role in gc_roles.values() if not role.get("lid")]
    if not (legacy and event.lid_address and event.chat.is_group):
        return gc_roles
    ids = await group.lid_map()
    if not ids:
        return gc_roles
    for role in legacy:
        role["members"] = current_members(role.get("members", []), ids)
        role["creator"] = ids.get(role.get("creator"), role.get("creator"))
        role["lid"] = True
    await save2db2(bot.group_dict, "groups")
    return gc_roles


async def prune_members(role: dict, group: Group) -> list:
    """Drops role members who left the group and returns the rest"""
    ids = await group.lid_map()
    if not ids:
        return role.get("members", [])
    members = current_members(role.get("members", []), ids)
    if members != role.get("members"):
        role["members"] = members
        await save2db2(bot.group_dict, "groups")
    return members


def set_members(role: dict, members: list):
    # Opted-out members who leave the role are forgotten
    role["members"] = members
    if role.get("quiet"):
        role["quiet"] = [m for m in role["quiet"] if m in members]


def update_mutes(chat_id: str, old: str, new: str | None = None):
    """Points role mutes at a renamed role, or drops them for a deleted one"""
    gc_dict = bot.group_dict.get(chat_id, {})
    for key in ("muted_roles", "mute_except_roles"):
        names = gc_dict.get(key)
        if names and old in names:
            names.discard(old)
            if new:
                names.add(new)


def is_creator(role: dict, event) -> bool:
    return role.get("creator") == event.from_user.id


def is_member(role: dict, event) -> bool:
    return event.from_user.id in role.get("members", [])


async def can_manage(event, role: dict, group: Group) -> bool:
    """
    Edit, delete, transfer, add to or remove from a role: locked roles need the owner,
    restricted roles admins, owner or sudoers; others also allow the creator.
    """
    user = event.from_user.id
    if role.get("locked"):
        return user_is_owner(user)
    if user_is_privileged(user):
        return True
    if not role.get("restricted") and is_creator(role, event):
        return True
    return await group.is_admin(user)


async def can_use(event, role: dict, group: Group) -> bool:
    """Join or tag a role: locked roles need the owner, restricted roles admins+"""
    user = event.from_user.id
    if role.get("locked"):
        return user_is_owner(user)
    if not role.get("restricted") or user_is_privileged(user):
        return True
    return await group.is_admin(user)


async def is_exempt(event, group: Group) -> bool:
    user = event.from_user.id
    return user_is_privileged(user) or await group.is_admin(user)


def name_error(name: str) -> str | None:
    if any(x in name for x in blocked_char):
        return "Role name contained invalid character(s)."
    if name.startswith(blocked_roles) or name in blocked_roles2:
        return "Role name is reserved."


async def display_name(client, user: str) -> str:
    # Contact names can be empty; the id is the last resort
    info = await client.contact.get_contact(jid.build_jid(user, "lid"))
    return info.PushName or info.FullName or user


async def allowed(event) -> bool:
    """Checks for group-only role commands; reacts when refusing"""
    if not event.chat.is_group:
        await event.react("🚫")
        return False
    user = event.from_user.id
    if user_is_privileged(user):
        return True
    if not chat_is_allowed(event):
        return False
    if not user_is_allowed(user):
        await event.react("⛔")
        return False
    return True


async def create_role(event, args, client):
    """
    Creates a role in the group. [Group Only]
    Users can create up to 10 roles per group; admins, owner and sudoers have no limit.

    Arguments:
        role_name: name of the role; case-insensitive, cannot contain spaces, dots or quotes,
            cannot start with admin/mod/owner/sudoer or be all/everyone
        -d "<description>" : [Optional] what the role is for; shown in the role list and info
        -c : [Optional] closed role; members can't join themselves, only be added by its
            creator or an admin
        -r : [Optional] restricted role; only admins, owner and sudoers can join, tag or manage it
            (flag usable by admins, owner and sudoers only)
        -cr : [Optional] locked role; like -r but joining and managing it is limited to the owner
            (flag usable by owner only)
    """
    if not await allowed(event):
        return
    user = event.from_user.id
    try:
        arg, args = get_args(
            ["-r", "store_true"],
            ["-cr", "store_true"],
            ["-c", "store_true"],
            "-d",
            to_parse=args,
            get_unknown=True,
        )
        args = args.casefold()
        if reason := name_error(args):
            return await event.reply(
                f"Creation of role with name: *{args}* failed!\n*Reason:* {reason}"
            )
        group = Group(event, client)
        gc_roles = await get_roles(event, group)
        if args in gc_roles:
            return await event.reply(
                f"Creation of role with name: *{args}* failed!\n*Reason:* Role already exists!"
            )
        created = sum(is_creator(role, event) for role in gc_roles.values())
        if created >= MAX_ROLES_PER_USER and not await is_exempt(event, group):
            return await event.reply(
                f"Creation of role with name: *{args}* failed!\n"
                f"*Reason:* You can create at most {MAX_ROLES_PER_USER} roles in a group."
            )
        if arg.r and not await is_exempt(event, group):
            await event.reply(
                "-r: Flag can only be used by admins/owner/sudoer, ignoring…"
            )
            arg.r = False
        if arg.cr and not user_is_owner(user):
            await event.reply("-cr: Flag can only be used by owner, ignoring…")
            arg.cr = False
        gc_roles.update(
            {
                args: {
                    "creator": user,
                    "members": [],
                    "restricted": arg.cr or arg.r,
                    "locked": arg.cr,
                    "closed": arg.c,
                    "description": (arg.d or "").strip(),
                    "lid": True,
                }
            }
        )
        await save2db2(bot.group_dict, "groups")
        await event.reply(role_action_msg.format("Created", args))
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def delete_role(event, args, client):
    """
    Deletes a role. [Group Only]
    The role's creator, group admins, owner and sudoers can delete it; restricted roles
    need admin/owner/sudoer and locked roles need the owner.
    Mutes set on the role are removed too.

    Arguments:
        role_name: name of the role to delete
    """
    if not await allowed(event):
        return
    try:
        args = args.casefold()
        group = Group(event, client)
        gc_roles = await get_roles(event, group)
        if args not in gc_roles:
            return await event.reply(
                f"Deletion of role with name: *{args}* failed!\n*Reason:* Role doesn't exist!"
            )
        if not await can_manage(event, gc_roles[args], group):
            return await event.reply("Insufficient permissions to delete this role")
        gc_roles.pop(args)
        update_mutes(event.chat.id, args)
        await save2db2(bot.group_dict, "groups")
        await event.reply(role_action_msg.format("Deleted", args))
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def edit_role(event, args, client):
    """
    Edits or renames a role. [Group Only]
    The role's creator, group admins, owner and sudoers can edit it; restricted roles
    need admin/owner/sudoer and locked roles need the owner.
    Options left out keep their current setting.

    Arguments:
        role_name: name of the role to edit
        -n <new_name> : [Optional] rename the role; same naming rules as new_role
        -d "<description>" : [Optional] set the description; -d "" removes it
        -c : [Optional] close the role (members can only be added by its creator or an admin)
        -o : [Optional] open the role, so anyone allowed can join
        -r : [Optional] make the role restricted (admins, owner and sudoers only)
        -cr : [Optional] make the role locked (owner only)
        -u : [Optional] remove the restriction or lock
    """
    if not await allowed(event):
        return
    user = event.from_user.id
    try:
        arg, args = get_args(
            ["-r", "store_true"],
            ["-cr", "store_true"],
            ["-u", "store_true"],
            ["-c", "store_true"],
            ["-o", "store_true"],
            "-n",
            "-d",
            to_parse=args,
            get_unknown=True,
        )
        args = args.casefold()
        group = Group(event, client)
        gc_roles = await get_roles(event, group)
        if args not in gc_roles:
            return await event.reply(
                f"Editing of role with name: *{args}* failed!\n*Reason:* Role doesn't exist!"
            )
        role = gc_roles[args]
        if not await can_manage(event, role, group):
            return await event.reply("Insufficient permissions to edit this role")
        new_name = None
        if arg.n:
            new_name = arg.n.casefold()
            if reason := name_error(new_name):
                return await event.reply(
                    f"Renaming of role with name: *{args}* to: *{new_name}* failed!\n*Reason:* {reason}"
                )
            if new_name in gc_roles:
                return await event.reply(
                    f"Renaming of role with name: *{args}* to: *{new_name}* failed!\n*Reason:* Role already exists!"
                )
        if arg.r and not await is_exempt(event, group):
            await event.reply(
                "-r: Flag can only be used by admins/owner/sudoer, ignoring…"
            )
            arg.r = False
        if arg.cr and not user_is_owner(user):
            await event.reply("-cr: Flag can only be used by owner, ignoring…")
            arg.cr = False
        if arg.u:
            role.update({"restricted": False, "locked": False})
        elif arg.cr or arg.r:
            role.update({"restricted": True, "locked": arg.cr})
        if arg.c or arg.o:
            role["closed"] = arg.c
        if arg.d is not None:
            role["description"] = arg.d.strip()
        if new_name:
            gc_roles[new_name] = gc_roles.pop(args)
            update_mutes(event.chat.id, args, new_name)
            await save2db2(bot.group_dict, "groups")
            return await event.reply(
                f"Renamed role with name: *{args}* to: *{new_name}* successfully!"
            )
        await save2db2(bot.group_dict, "groups")
        await event.reply(role_action_msg.format("Edited", args))
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def exit_role(event, args, client):
    """
    Leaves a role you are a member of. [Group Only]

    Arguments:
        role_name: name of the role to leave
    """
    if not await allowed(event):
        return
    try:
        args = args.casefold()
        gc_roles = await get_roles(event, Group(event, client))
        if args not in gc_roles:
            return await event.reply(
                f"Exiting of role with name: *{args}* failed!\n*Reason:* Role doesn't exist!"
            )
        role = gc_roles[args]
        if not is_member(role, event):
            return await event.reply("You're not a member of this role.")
        set_members(role, [m for m in role["members"] if m != event.from_user.id])
        await save2db2(bot.group_dict, "groups")
        await event.reply(role_action_msg.format("Left", args))
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def join_role(event, args, client):
    """
    Joins an existing role. [Group Only]
    Restricted roles can only be joined by admins, owner and sudoers; locked roles by the owner.
    Closed roles can't be joined; their creator or an admin has to add you.

    Arguments:
        role_name: name of the role to join
    """
    if not await allowed(event):
        return
    try:
        args = args.casefold()
        group = Group(event, client)
        gc_roles = await get_roles(event, group)
        if args not in gc_roles:
            return await event.reply(
                f"Joining of role with name: *{args}* failed!\n*Reason:* Role doesn't exist!"
            )
        role = gc_roles[args]
        if is_member(role, event):
            return await event.reply("Already a member of this role.")
        if not await can_use(event, role, group):
            return await event.reply(
                "Insufficient permissions to become a member of this role"
            )
        if role.get("closed") and not await can_manage(event, role, group):
            return await event.reply(
                "This role is closed; ask its creator or an admin to add you."
            )
        role.setdefault("members", []).append(event.from_user.id)
        await save2db2(bot.group_dict, "groups")
        await event.reply(role_action_msg.format("Joined", args))
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def users_from_event(event, args: str, role_name: str, group: Group):
    """
    The replied user and mentioned users as LIDs, plus how many of them
    aren't in the group.
    """
    users = []
    if event.reply_to_message:
        users.append(event.reply_to_message.from_user.id)
    if args != role_name or not event.reply_to_message:
        users.extend(get_mentioned(args))
    ids = await group.lid_map()
    found = list(dict.fromkeys(ids[u] for u in users if u in ids))
    missing = len(set(users) - set(ids))
    return found, missing


async def add_to_role(event, args, client):
    """
    Adds users to a role. [Group Only]
    The role's creator, group admins, owner and sudoers can do this; restricted roles
    need admin/owner/sudoer and locked roles need the owner.

    Usage:
        add2role -r <role_name> @user1 @user2 ...
        add2role <role_name> (as a reply to the user to add)

    Arguments:
        -r <role_name> : role to add to; when replying without -r, the whole argument is the role name
        mentions : users to add (the replied user is also added)
    """
    if not await allowed(event):
        return
    try:
        arg, args = get_args(
            "-r",
            to_parse=args,
            get_unknown=True,
        )
        if not arg.r and not event.reply_to_message:
            return await event.reply("kindly specify a role name with '-r'")
        if not arg.r and event.reply_to_message:
            arg.r = args
        if not (event.reply_to_message or args):
            return await event.reply("Supply users through mentions or reply!")
        arg.r = arg.r.casefold()
        group = Group(event, client)
        gc_roles = await get_roles(event, group)
        if arg.r not in gc_roles:
            return await event.reply(f"Role with name: {arg.r} doesn't exist!")
        role = gc_roles[arg.r]
        if not await can_manage(event, role, group):
            return await event.reply(
                "Insufficient permissions to batch add members to this role"
            )
        users, missing = await users_from_event(event, args, arg.r, group)
        members = role.setdefault("members", [])
        new = [u for u in users if u not in members]
        notes = []
        if already := len(users) - len(new):
            notes.append(f"{already} already in the role")
        if missing:
            notes.append(f"{missing} not in this group")
        note = f" ({', '.join(notes)})" if notes else ""
        if not new:
            return await event.reply(f"No new members to add to the role{note}.")
        members.extend(new)
        await save2db2(bot.group_dict, "groups")
        await event.reply(
            f"Added {len(new)} user(s) to role with name: *{arg.r}*{note}."
        )
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def remove_from_role(event, args, client):
    """
    Removes users from a role. [Group Only]
    The role's creator, group admins, owner and sudoers can do this; restricted roles
    need admin/owner/sudoer and locked roles need the owner.

    Usage:
        rm_from_role -r <role_name> @user1 @user2 ...
        rm_from_role <role_name> (as a reply to the user to remove)

    Arguments:
        -r <role_name> : role to remove from; when replying without -r, the whole argument is the role name
        mentions : users to remove (the replied user is also removed)
    """
    if not await allowed(event):
        return
    try:
        arg, args = get_args(
            "-r",
            to_parse=args,
            get_unknown=True,
        )
        if not arg.r and not event.reply_to_message:
            return await event.reply("kindly specify a role name with '-r'")
        if not arg.r and event.reply_to_message:
            arg.r = args
        if not (event.reply_to_message or args):
            return await event.reply("Supply users through mentions or reply!")
        arg.r = arg.r.casefold()
        group = Group(event, client)
        gc_roles = await get_roles(event, group)
        if arg.r not in gc_roles:
            return await event.reply(f"Role with name: {arg.r} doesn't exist!")
        role = gc_roles[arg.r]
        if not await can_manage(event, role, group):
            return await event.reply(
                "Insufficient permissions to batch remove members from this role"
            )
        users, _ = await users_from_event(event, args, arg.r, group)
        members = role.setdefault("members", [])
        gone = [u for u in users if u in members]
        if not gone:
            return await event.reply("None of those users are in the role.")
        set_members(role, [m for m in members if m not in gone])
        await save2db2(bot.group_dict, "groups")
        await event.reply(
            f"Removed {len(gone)} user(s) from role with name: *{arg.r}*."
        )
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def transfer_role(event, args, client):
    """
    Makes another group member the role's creator. [Group Only]
    The role's creator, group admins, owner and sudoers can do this; restricted roles
    need admin/owner/sudoer and locked roles need the owner.

    Usage:
        transfer_role <role_name> @user
        transfer_role <role_name> (as a reply to the new creator)
    """
    if not await allowed(event):
        return
    try:
        role_name, _, rest = args.partition(" ")
        role_name = role_name.casefold()
        group = Group(event, client)
        gc_roles = await get_roles(event, group)
        if role_name not in gc_roles:
            return await event.reply(f"Role with name: {role_name} doesn't exist!")
        role = gc_roles[role_name]
        if not await can_manage(event, role, group):
            return await event.reply("Insufficient permissions to transfer this role")
        users = get_mentioned(rest)
        if not users and event.reply_to_message:
            users = [event.reply_to_message.from_user.id]
        if len(users) != 1:
            return await event.reply(
                "Mention or reply to exactly one user to transfer the role to."
            )
        ids = await group.lid_map()
        if not (new_creator := ids.get(users[0])):
            return await event.reply("That user isn't in this group.")
        if new_creator == role.get("creator"):
            return await event.reply("That user already owns this role.")
        role["creator"] = new_creator
        await save2db2(bot.group_dict, "groups")
        await event.reply(
            f"Transferred role with name: *{role_name}* to "
            f"{await display_name(client, new_creator)} successfully!"
        )
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def role_tags(event, args, client):
    """
    Turns tags from a role you're in on or off, without leaving it. [Group Only]

    Usage:
        role_tags <role_name> [on|off] (without on/off, toggles)
    """
    if not await allowed(event):
        return
    try:
        role_name, _, state = args.casefold().partition(" ")
        state = state.strip()
        if state not in ("", "on", "off"):
            return await event.reply("Use on or off, or leave it out to toggle.")
        gc_roles = await get_roles(event, Group(event, client))
        if role_name not in gc_roles:
            return await event.reply(f"Role with name: {role_name} doesn't exist!")
        role = gc_roles[role_name]
        if not is_member(role, event):
            return await event.reply("You're not a member of this role.")
        user = event.from_user.id
        quiet = role.setdefault("quiet", [])
        off = (user not in quiet) if not state else state == "off"
        role["quiet"] = [m for m in quiet if m != user] + ([user] if off else [])
        await save2db2(bot.group_dict, "groups")
        await event.reply(
            f"Tags from role *{role_name}* are now {'off' if off else 'on'} for you."
        )
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def my_roles(event, args, client):
    """Lists the roles you're in, in this group. [Group Only]"""
    if not await allowed(event):
        return
    try:
        gc_roles = await get_roles(event, Group(event, client))
        user = event.from_user.id
        msg = ""
        for role_name, role in gc_roles.items():
            if not is_member(role, event):
                continue
            off = " _(tags off)_" if user in role.get("quiet", []) else ""
            msg += f"\n- {role_name}{off}"
        await event.reply(
            f"*Your roles:*{msg}" if msg else "*You're not in any role in this group.*"
        )
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def tag_roles(event, _, client):
    """
    Automatic handler (not a command): tags all members of every role mentioned as @role_name
    (or @role_names) in a group message or caption. If the message is a reply, the tag replies
    to that message and says who tagged.
    Restricted roles can only be tagged by admins, owner and sudoers; locked roles by the owner.
    Members who turned the role's tags off aren't tagged.
    Each role can be tagged once a minute; admins, owner and sudoers are exempt.
    """
    try:
        if not event.chat.is_group:
            return
        if not (text := event.text or event.caption):
            return
        if not (gc_roles := bot.group_dict.get(event.chat.id, {}).get("roles")):
            return
        names = list(dict.fromkeys(r for r, _ in find_role_mentions(text, gc_roles)))
        if not names:
            return
        user = event.from_user.id
        if not user_is_privileged(user):
            if not (chat_is_allowed(event) and user_is_allowed(user)):
                return
        group = Group(event, client)
        gc_roles = await get_roles(event, group)
        by = ""
        if event.reply_to_message:
            # The tag quotes the replied message, so the tagger isn't visible.
            # Push names can be empty; fall back to the stored contact name
            name = event.from_user.name or await display_name(client, user)
            by = f" _(by {name})_"
        for role_name in names:
            if not (role := gc_roles.get(role_name)):
                continue
            if not await can_use(event, role, group):
                continue
            key = (event.chat.id, role_name)
            if time.time() - last_tagged.get(key, 0) < TAG_COOLDOWN:
                if not await is_exempt(event, group):
                    await event.react("⏳")
                    continue
            members = await prune_members(role, group)
            quiet = set(role.get("quiet", []))
            if not (members := [m for m in members if m not in quiet]):
                continue
            last_tagged[key] = time.time()
            await clean_reply(
                event,
                event.reply_to_message,
                "reply",
                f"_*Tagged all {role_name}!*_{by}",
                ghost_mentions=tag_all_users_in_role(members),
            )
            await asyncio.sleep(1)
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def list_roles(event, args, client):
    """Lists all roles in the group with their creators and member counts. [Group Only]"""
    if not event.chat.is_group:
        return await event.react("🚫")
    gc_roles = await get_roles(event, Group(event, client))
    msg = ""
    for no, (role_name, role) in enumerate(gc_roles.items(), start=1):
        creator = await display_name(client, role.get("creator"))
        count = len(role.get("members", []))
        closed = " 🔒" if role.get("closed") else ""
        msg += f"\n{no}. {role_name}{closed} ({count}) *Created by:* {creator}"
        if desc := role.get("description"):
            msg += f"\n    _{desc}_"
    if not msg:
        resp = "*No roles found in this group.*"
    else:
        resp = f"*List of Roles in @{jid.Jid2String(event.chat.jid)}:*{msg}"
        if "🔒" in msg:
            resp += "\n\n🔒: *Closed; ask its creator or an admin to add you.*"

    for text in split_text(resp):
        event = await event.reply(text)


async def role_info(event, args, client):
    """Shows a role's description, creator, settings and members."""
    gc_roles = await get_roles(event, Group(event, client))
    role = gc_roles.get(args)
    quiet = set(role.get("quiet", []))
    users = ""
    for user in role.get("members", []):
        off = " _(tags off)_" if user in quiet else ""
        users += f"\n- {await display_name(client, user)}{off}"
    desc = f"*Description:* {d}\n" if (d := role.get("description")) else ""
    msg = (
        f"*Role Name:* {args}\n"
        f"{desc}"
        f"*Creator:* {await display_name(client, role.get('creator'))}\n"
        f"*Closed:* {bool(role.get('closed'))}\n"
        f"*Restricted:* {role.get('restricted')}\n"
        f"*Locked:* {role.get('locked')}\n\n"
        f"*Members ({len(role.get('members', []))}):*{users}"
    )
    await event.reply(msg)


async def roles(event, args, client):
    """
    Shows the role commands, lists the group's roles, or shows info on a role.

    Arguments:
        None : show the list of role commands
        -l/--list : list all roles in the group [Group Only]
        role_name : show info on that role (unknown names show the command list)
    """
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        if args in ("-l", "--list"):
            return await list_roles(event, args, client)
        elif args:
            args = args.casefold()
            gc_roles = bot.group_dict.get(event.chat.id, {}).get("roles", {})
            if gc_roles.get(args):
                return await role_info(event, args, client)
        pre = conf.CMD_PREFIX
        msg = f"""{pre}new_role <name> [-d "<description>"] [-c] [-r|-cr] - *Create a role (-c: closed, members are added by its creator/admins; -r: restricted, admins+; -cr: locked, owner only)*
{pre}del_role <name> - *Delete a role (creator/admin/owner/sudoer)*
{pre}edit_role <name> [-n <new_name>] [-d "<description>"] [-c|-o] [-r|-cr|-u] - *Rename a role or change its settings (-o: open, -u: unrestrict) (creator/admin/owner/sudoer)*
{pre}transfer_role <name> @user - *Make someone else the role's creator (or reply to them)*
{pre}join_role <name> - *Join a role*
{pre}exit_role <name> - *Leave a role*
{pre}role_tags <name> [on|off] - *Turn tags from a role you're in on or off*
{pre}my_roles - *List the roles you're in*
{pre}add2role -r <name> @users - *Add users to a role (or reply with: add2role <name>)*
{pre}rm_from_role -r <name> @users - *Remove users from a role (or reply with: rm_from_role <name>)*
{pre}roles -l - *List all roles in the group*
{pre}roles <name> - *Show info on a role*
{pre}roles - *Get this message again*

Tag a role's members by writing @<name> (or @<name>s) in a group message; each role can be tagged once a minute.
Users can create up to {MAX_ROLES_PER_USER} roles per group.
Admins can also mute a role with {pre}mute."""
        await event.reply(msg)
    except Exception:
        await logger(Exception)
        await event.react("❌")


bot.add_handler(create_role, "new_role", require_args=True)
bot.add_handler(delete_role, "del_role", require_args=True)
bot.add_handler(edit_role, "edit_role", require_args=True)
bot.add_handler(exit_role, "exit_role", require_args=True)
bot.add_handler(join_role, "join_role", require_args=True)
bot.add_handler(add_to_role, "add2role", require_args=True)
bot.add_handler(remove_from_role, "rm_from_role", require_args=True)
bot.add_handler(transfer_role, "transfer_role", require_args=True)
bot.add_handler(role_tags, "role_tags", require_args=True)
bot.add_handler(my_roles, "my_roles")
bot.add_handler(tag_roles)
