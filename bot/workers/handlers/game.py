from bot.config import conf


async def were_info(event, args, client):
    msg = "In Werewolf, there are two teams, village and wolves. The villagers try to get rid of all of the wolves, and the wolves try to kill all of the villagers.\n"
    msg += "There are two phases, night and day. During night, the wolf/wolves choose a target to kill, and some special village roles like seer perform their actions. "
    msg += "During day, the village discusses everything and chooses someone to lynch. "
    msg += "Once you die, Please don't talk in the group chat the game is taking place.\n\n"
    msg += "To join a game, use `{0} -j`.\n"
    msg += "For a list of roles, use the command `{0} -r`. For information on a particular role, use `{0} -r role`. For statistics on the current game, use `{0} -s`. "
    msg += "For a list of commands, use `{0} -l`. For help on a command, use `{0} -h command`. To see the in-game time, use `{0} -t`.\n\n"
    return await event.reply(msg.format(f"{conf.CMD_PREFIX}werewolf"))
