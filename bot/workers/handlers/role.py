import asyncio

from bot import jid
from bot.config import bot, conf
from bot.utils.bot_utils import split_text
from bot.utils.db_utils import save2db2
from bot.utils.log_utils import logger
from bot.utils.msg_utils import (
    chat_is_allowed,
    clean_reply,
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


async def create_role(event, args, client):
    """
    Creates a role in the group. [Group Only]

    Arguments:
        role_name: name of the role; case-insensitive, cannot contain spaces, dots or quotes,
            cannot start with admin/mod/owner/sudoer or be all/everyone
        -r : [Optional] restricted role; only admins, owner and sudoers can join, tag or manage it
            (flag usable by admins, owner and sudoers only)
        -cr : [Optional] locked role; like -r but joining and managing it is limited to the owner
            (flag usable by owner only)
    """
    if not event.chat.is_group:
        return await event.react("🚫")
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        arg, args = get_args(
            ["-r", "store_true"],
            ["-cr", "store_true"],
            to_parse=args,
            get_unknown=True,
        )
        args = args.casefold()
        if any(x in args for x in blocked_char):
            return await event.reply(
                f"Creation of role with name: *{args}* failed!\n*Reason:* Role name contained invalid character(s)."
            )
        if args.startswith(blocked_roles) or args in blocked_roles2:
            return await event.reply(
                f"Creation of role with name: *{args}* is blocked!"
            )
        chat_id = event.chat.id
        gc_roles = bot.group_dict.setdefault(chat_id, {}).setdefault("roles", {})

        if args in gc_roles:
            return await event.reply(
                f"Creation of role with name: *{args}* failed!\n*Reason:* Role already exists!"
            )
        if arg.r:
            group_info = await client.get_group_info(event.chat.jid)
        if arg.r and not (
            user_is_privileged(user) or user_is_admin(user, group_info.Participants)
        ):
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
                    "creator": event.user.id,
                    "members": [],
                    "restricted": arg.cr or arg.r,
                    "locked": arg.cr,
                    "lid": event.lid_address,
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
    Only the role's creator, owner or sudoers can delete it; restricted roles also need
    admin/owner/sudoer and locked roles need the owner.

    Arguments:
        role_name: name of the role to delete
    """
    if not event.chat.is_group:
        return await event.react("🚫")
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        args = args.casefold()
        chat_id = event.chat.id
        gc_roles = bot.group_dict.setdefault(chat_id, {}).setdefault("roles", {})
        if args not in gc_roles:
            return await event.reply(
                f"Deletion of role with name: *{args}* failed!\n*Reason:* Role doesn't exist!"
            )
        role = gc_roles.get(args)
        if role.get("restricted"):
            group_info = await client.get_group_info(event.chat.jid)
        if (
            role.get("restricted")
            and not (
                user_is_privileged(user) or user_is_admin(user, group_info.Participants)
            )
        ) or (role.get("locked") and not user_is_owner(user)):
            return await event.reply("Insufficient permissions to delete this role")
        if role.get("creator") != event.user.id and not user_is_privileged(user):
            return await event.reply("Insufficient permissions to delete this role")
        gc_roles.pop(args)
        await save2db2(bot.group_dict, "groups")
        await event.reply(role_action_msg.format("Deleted", args))
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def edit_role(event, args, client):
    """
    Edits or renames a role. [Group Only]
    Only the role's creator, owner or sudoers can edit it; restricted roles also need
    admin/owner/sudoer and locked roles need the owner.
    The restriction is reset on every edit: omitting -r/-cr makes the role unrestricted.

    Arguments:
        role_name: name of the role to edit
        -r : [Optional] make the role restricted (admins, owner and sudoers only)
        -cr : [Optional] make the role locked (owner only)
        -n <new_name> : [Optional] rename the role; same naming rules as new_role
    """
    if not event.chat.is_group:
        return await event.react("🚫")
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        arg, args = get_args(
            ["-r", "store_true"],
            ["-cr", "store_true"],
            "-n",
            to_parse=args,
            get_unknown=True,
        )
        args = args.casefold()
        chat_id = event.chat.id
        gc_roles = bot.group_dict.setdefault(chat_id, {}).setdefault("roles", {})
        if args not in gc_roles:
            return await event.reply(
                f"Editing of role with name: *{args}* failed!\n*Reason:* Role doesn't exist!"
            )
        role = gc_roles.get(args)
        if role.get("restricted"):
            group_info = await client.get_group_info(event.chat.jid)
        if (
            role.get("restricted")
            and not (
                user_is_privileged(user) or user_is_admin(user, group_info.Participants)
            )
        ) or (role.get("locked") and not user_is_owner(user)):
            return await event.reply("Insufficient permissions to edit this role")
        if role.get("creator") != event.user.id and not user_is_privileged(user):
            return await event.reply("Insufficient permissions to edit this role")
        new_name = None
        if arg.n:
            new_name = arg.n.casefold()
            if any(x in new_name for x in blocked_char):
                return await event.reply(
                    f"Renaming of role with name: *{args}* to: *{new_name}* failed!\n*Reason:* New Role name contained invalid character(s)."
                )
            if new_name.startswith(blocked_roles) or new_name in blocked_roles2:
                return await event.reply(
                    f"Renaming of role with name: *{args}* to: *{new_name}* is blocked!"
                )
            if new_name in gc_roles:
                return await event.reply(
                    f"Renaming of role with name: *{args}* to: *{new_name}* failed!\n*Reason:*Role already exists!"
                )
        if arg.r and not user_is_privileged(user):
            group_info = await client.get_group_info(event.chat.jid)
            if not user_is_admin(user, group_info.Participants):
                await event.reply(
                    "-r: Flag can only be used by admins/owner/sudoer, ignoring…"
                )
                arg.r = False
        if arg.cr and not user_is_owner(user):
            await event.reply("-cr: Flag can only be used by owner, ignoring…")
            arg.cr = False
        role.update({"restricted": arg.cr or arg.r, "locked": arg.cr})
        if new_name:
            gc_roles[new_name] = gc_roles.pop(args)
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
    if not event.chat.is_group:
        return await event.react("🚫")
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        args = args.casefold()
        chat_id = event.chat.id
        gc_roles = bot.group_dict.setdefault(chat_id, {}).setdefault("roles", {})
        if args not in gc_roles:
            return await event.reply(
                f"Exiting of role with name: *{args}* failed!\n*Reason:* Role doesn't exist!"
            )
        role = gc_roles.get(args)
        if event.user.id not in role.get("members"):
            return await event.reply("You're not a member of this role.")
        role.setdefault("members", []).remove(event.user.id)
        await save2db2(bot.group_dict, "groups")
        await event.reply(role_action_msg.format("Left", args))
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def join_role(event, args, client):
    """
    Joins an existing role. [Group Only]
    Restricted roles can only be joined by admins, owner and sudoers; locked roles by the owner.

    Arguments:
        role_name: name of the role to join
    """
    if not event.chat.is_group:
        return await event.react("🚫")
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        args = args.casefold()
        chat_id = event.chat.id
        gc_roles = bot.group_dict.setdefault(chat_id, {}).setdefault("roles", {})
        if args not in gc_roles:
            return await event.reply(
                f"Joining of role with name: *{args}* failed!\n*Reason:* Role doesn't exist!"
            )
        role = gc_roles.get(args)
        user_id = event.user.id
        if user_id in role.get("members"):
            return await event.reply("Already a member of this role.")
        if role.get("restricted"):
            group_info = await client.get_group_info(event.chat.jid)
        if (
            role.get("restricted")
            and not (
                user_is_privileged(user) or user_is_admin(user, group_info.Participants)
            )
        ) or (role.get("locked") and not user_is_owner(user)):
            return await event.reply(
                "Insufficient permissions to become a member of this role"
            )
        role.setdefault("members", []).append(user_id)
        await save2db2(bot.group_dict, "groups")
        await event.reply(role_action_msg.format("Joined", args))
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def add_to_role(event, args, client):
    """
    Adds users to a role. [Group Only]
    Only the role's creator, owner or sudoers can do this; restricted roles also need
    admin/owner/sudoer and locked roles need the owner.

    Usage:
        add2role -r <role_name> @user1 @user2 ...
        add2role <role_name> (as a reply to the user to add)

    Arguments:
        -r <role_name> : role to add to; when replying without -r, the whole argument is the role name
        mentions : users to add (the replied user is also added)
    """
    if not event.chat.is_group:
        return await event.react("🚫")
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
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
        chat_id = event.chat.id
        gc_roles = bot.group_dict.setdefault(chat_id, {}).setdefault("roles", {})
        if arg.r not in gc_roles:
            return await event.reply(f"Role with name: {arg.r} doesn't exist!")
        role = gc_roles.get(arg.r)
        if role.get("restricted"):
            group_info = await client.get_group_info(event.chat.jid)
        if (
            role.get("restricted")
            and not (
                user_is_privileged(user) or user_is_admin(user, group_info.Participants)
            )
        ) or (role.get("locked") and not user_is_owner(user)):
            return await event.reply(
                "Insufficient permissions to batch add members to this role"
            )
        if role.get("creator") != event.user.id and not user_is_privileged(user):
            return await event.reply(
                "Insufficient permissions to batch add members to this role"
            )
        members = []
        if event.reply_to_message:
            members.append(event.reply_to_message.user.id)
        if args != arg.r or not event.reply_to_message:
            members.extend(get_mentioned(args))
        members = list(set(members))
        for member in list(members):
            if member in role.get("members"):
                await event.reply(f"@{member} is already a member of this role.")
                await asyncio.sleep(2)
                members.remove(member)
        if not members:
            return await event.reply("No new members to add to role was supplied.")
        role.setdefault("members", []).extend(members)
        await save2db2(bot.group_dict, "groups")
        await event.reply(role_action_msg.format("Added users to", arg.r))
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def remove_from_role(event, args, client):
    """
    Removes users from a role. [Group Only]
    Only the role's creator, owner or sudoers can do this; restricted roles also need
    admin/owner/sudoer and locked roles need the owner.

    Usage:
        rm_from_role -r <role_name> @user1 @user2 ...
        rm_from_role <role_name> (as a reply to the user to remove)

    Arguments:
        -r <role_name> : role to remove from; when replying without -r, the whole argument is the role name
        mentions : users to remove (the replied user is also removed)
    """
    if not event.chat.is_group:
        return await event.react("🚫")
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
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
        chat_id = event.chat.id
        gc_roles = bot.group_dict.setdefault(chat_id, {}).setdefault("roles", {})
        if arg.r not in gc_roles:
            return await event.reply(f"Role with name: {arg.r} doesn't exist!")
        role = gc_roles.get(arg.r)
        if role.get("restricted"):
            group_info = await client.get_group_info(event.chat.jid)
        if (
            role.get("restricted")
            and not (
                user_is_privileged(user) or user_is_admin(user, group_info.Participants)
            )
        ) or (role.get("locked") and not user_is_owner(user)):
            return await event.reply(
                "Insufficient permissions to batch remove members to this role"
            )
        if role.get("creator") != event.user.id and not user_is_privileged(user):
            return await event.reply(
                "Insufficient permissions to batch remove members to this role"
            )
        members = []
        if event.reply_to_message:
            members.append(event.reply_to_message.user.id)
        if args != arg.r or not event.reply_to_message:
            members.extend(get_mentioned(args))
        members = list(set(members))
        for member in list(members):
            if member not in role.get("members"):
                await event.reply(f"@{member} is not a member of this role.")
                await asyncio.sleep(2)
                members.remove(member)
        if not members:
            return await event.reply("No new members to remove from role was supplied.")
        members = list(set(role.get("members")) - set(members))
        role["members"] = members
        await save2db2(bot.group_dict, "groups")
        await event.reply(role_action_msg.format("Removed users from", arg.r))
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def tag_roles(event, _, client):
    """
    Automatic handler (not a command): tags all members of every role mentioned as @role_name
    in a group message or caption. If the message is a reply, the tag replies to that message.
    Restricted roles can only be tagged by admins, owner and sudoers; locked roles by the owner.
    """
    try:
        if not (event.text or event.caption):
            return
        if not event.chat.is_group:
            return
        chat_id = event.chat.id
        user = event.from_user.id
        gc_roles = bot.group_dict.setdefault(chat_id, {}).setdefault("roles", {})
        if not gc_roles:
            return
        text = event.text or event.caption
        for role_name in gc_roles:
            if ("@" + role_name) not in (text.casefold()):
                continue
            role = gc_roles.get(role_name)
            if not role.get("members"):
                continue
            if role.get("restricted") and not user_is_privileged(user):
                group_info = await client.get_group_info(event.chat.jid)
                if not user_is_admin(user, group_info.Participants):
                    continue
            if role.get("locked") and not user_is_owner(user):
                continue
            if not role.get("lid") and event.lid_address:
                await event.reply(
                    "*Group has been migrated to lid, kindly delete and recreate role!*"
                )
                continue
            tags = tag_all_users_in_role(role.get("members"))
            await clean_reply(
                event,
                event.reply_to_message,
                "reply",
                f"_*Tagged all {role_name}!*_",
                ghost_mentions=tags,
            )
            await asyncio.sleep(1)
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def list_roles(event, args, client):
    """Lists all roles in the group with their creators. [Group Only]"""
    if not event.chat.is_group:
        return await event.react("🚫")
    msg = ""
    gc_roles = bot.group_dict.setdefault(event.chat.id, {}).setdefault("roles", {})
    no = 1
    warning = False
    for role_name in gc_roles:
        role = gc_roles.get(role_name)
        creator = role.get("creator")
        warn = "⚠️" if not role.get("lid") and event.lid_address else ""
        if warn and not warning:
            warning = True
        # info = await client.contact.get_contact(jid.build_jid(creator))
        # name = info.FullName or info.PushName
        msg += f"\n{no}. {role_name} {warn} *Created by:* @{creator}"

        no += 1
    if not msg:
        resp = "*No roles found in this group.*"
    else:
        resp = f"*List of Roles in @{jid.Jid2String(event.chat.jid)}:*{msg}"
        if warning:
            resp += "\n\n⚠️: *Roles with this emoji are currently broken please delete and recreate!*"

    for text in split_text(resp):
        event = await event.reply(text)


async def role_info(event, args, client):
    """Shows a role's creator, restriction/lock status and members."""
    gc_roles = bot.group_dict.setdefault(event.chat.id, {}).setdefault("roles", {})
    role = gc_roles.get(args)
    users = ""
    for user in role.get("members"):
        server = "s.whatsapp.net" if not role.get("lid") else "lid"
        info = await client.contact.get_contact(jid.build_jid(user, server))
        name = info.PushName
        users += f"\n- {name}"
    msg = (
        f"*Role Name:* {args}\n"
        f"*Creator:* @{role.get('creator')}\n"
        f"*Restricted:* {role.get('restricted')}\n"
        f"*Locked:* {role.get('locked')}\n\n"
        f"*Members:*{users}"
    )
    if not role.get("lid") and event.lid_address:
        msg += "\n\n*Status:* Currently unusable due to migration of group to lid. Kindly delete & recreate the role!"
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
            gc_roles = bot.group_dict.setdefault(event.chat.id, {}).setdefault(
                "roles", {}
            )
            if gc_roles.get(args):
                return await role_info(event, args, client)
        pre = conf.CMD_PREFIX
        msg = f"""{pre}new_role <name> [-r|-cr] - *Create a role (-r: restricted, admins+; -cr: locked, owner only)*
{pre}del_role <name> - *Delete a role (creator/owner/sudoer)*
{pre}edit_role <name> [-n <new_name>] [-r|-cr] - *Rename or change restriction of a role (creator/owner/sudoer)*
{pre}join_role <name> - *Join a role*
{pre}exit_role <name> - *Leave a role*
{pre}add2role -r <name> @users - *Add users to a role (or reply with: add2role <name>)*
{pre}rm_from_role -r <name> @users - *Remove users from a role (or reply with: rm_from_role <name>)*
{pre}roles -l - *List all roles in the group*
{pre}roles <name> - *Show info on a role*
{pre}roles - *Get this message again*

Tag a role's members by writing @<name> in a group message."""
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
bot.add_handler(tag_roles)
