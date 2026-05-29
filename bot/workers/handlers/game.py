import asyncio
import random
from bot.config import bot, conf
from bot.games.werewolf.game import Game
from bot.games.werewolf.logic import game_loop
from bot.games.werewolf.roles import gamemodes
from bot.games.register import register_for_a_game
from bot.games.werewolf.defaults import DETECTIVE_REVEAL_CHANCE


async def werewolf_handler(event, args, client):
    """
    Werewolf Game Handler

    Commands:
    -j : Join game
    -s : Game status
    -start : Start game
    -mode <mode> : Set game mode
    -restricted : Enable restricted mode (when starting)
    """
    if not args:
        return await were_info(event, args, client)

    res = register_for_a_game("werewolf", event)
    if not res:
         return
    if res == "started":
         current_games = bot.current_games_dict.get("werewolf", {})
         game = current_games.get(event.chat.id)
         if game and not game.waiting:
             if event.text.startswith(f"{conf.CMD_PREFIX}lynch"):
                 return await handle_game_command(game, event, "lynch")
             if event.text.startswith(f"{conf.CMD_PREFIX}id"):
                 return await handle_game_command(game, event, "id")
         return

    current_games = bot.current_games_dict.setdefault("werewolf", {})
    game = current_games.get(event.chat.id)

    if "-j" in args:
        if not game or isinstance(game, dict):
            game = Game(event)
            current_games[event.chat.id] = game
            return await event.reply("Game lobby created! Use `-j` to join.")
        return await game.join(event)

    if "-s" in args:
        if not game or isinstance(game, dict):
            return await event.reply("No game in progress in this chat.")
        return await game.status(event)

    if "-start" in args:
        if not game or isinstance(game, dict):
            return await event.reply("No game lobby created. Use `-j` to start one.")
        if not game.waiting:
            return await event.reply("Game is already in progress.")

        if "-restricted" in args:
            game.restricted = True

        game.set_each_role_numbers_and_pool()
        if game.total_players < game.min_players:
             return await event.reply(f"Not enough players for mode *{game.mode}*! Need at least {game.min_players}.")

        asyncio.create_task(game_loop(game))
        return await event.reply(f"Game starting with mode *{game.mode}*! Restricted: {game.restricted}. Check your PMs for roles.")

    if "-mode" in args:
        if game and not isinstance(game, dict) and not game.waiting:
            return await event.reply("Cannot change mode after game started.")

        mode_name = args.replace("-mode", "").replace("-restricted", "").strip().lower()
        if not mode_name:
            msg = "*Available Gamemodes:*\n"
            for m, data in gamemodes.items():
                msg += f"- *{m}*: {data['description']}\n"
            return await event.reply(msg)

        if mode_name not in gamemodes:
            return await event.reply(f"Mode *{mode_name}* not found.")

        if not game or isinstance(game, dict):
            game = Game(event, mode=mode_name)
            current_games[event.chat.id] = game
            return await event.reply(f"Game lobby created with mode *{mode_name}*! Use `-j` to join.")
        else:
            game.requested_mode = mode_name
            return await event.reply(f"Mode set to *{mode_name}*.")


async def handle_game_command(game, event, cmd_type):
    if cmd_type == "lynch":
        if not game.day:
             return await event.reply("You can only lynch during the day!")

        player = game.get_player_by_user_id(event.from_user.id)
        if not player or player.is_dead:
             return

        args = event.text.split(maxsplit=1)
        if len(args) < 2:
             return await event.reply("Usage: .lynch <id or name>")

        target_str = args[1].strip()
        target = game.get_player_by_id(target_str)
        if not target:
             for p in game.players_alive_list:
                  if target_str.lower() in p.name.lower():
                       target = p
                       break

        if not target or not target.is_alive:
             return await event.reply("Invalid target.")

        player.vote = target.user_id
        await event.reply(f"You voted to lynch {target.name}!")

    elif cmd_type == "id":
        if not game.day:
             return await event.reply("You can only use id during the day!")

        player = game.get_player_by_user_id(event.from_user.id)
        if not player or player.role != "detective" or player.is_dead:
             return

        if getattr(game, "detective_acted", False):
             return await event.reply("You have already used your ability today.")

        args = event.text.split(maxsplit=1)
        if len(args) < 2:
             return await event.reply("Usage: .id <id or name>")

        target_str = args[1].strip()
        target = game.get_player_by_id(target_str)
        if not target:
             for p in game.players_alive_list:
                  if target_str.lower() in p.name.lower():
                       target = p
                       break

        if not target or not target.is_alive:
             return await event.reply("Invalid target.")

        game.detective_acted = True
        await bot.client.send_message(player.user_id, f"Your investigation reveals that {target.name} is a *{target.role}*.")

        if random.random() < DETECTIVE_REVEAL_CHANCE:
             await game.wolfchat(f"The detective has been revealed! It is {player.name}.")


async def werewolf_restriction_handler(client, event):
    if not event.chat.is_group:
        return

    current_games = bot.current_games_dict.get("werewolf", {})
    game = current_games.get(event.chat.id)

    if not game or isinstance(game, dict) or game.waiting or not game.restricted:
        return

    player = game.get_player_by_user_id(event.from_user.id)
    if not player or player.is_dead:
        try:
            await event.delete()
        except Exception:
            pass


async def were_info(event, args, client):
    msg = "*Werewolf Game*\n\n"
    msg += f"To join/create: `{conf.CMD_PREFIX}werewolf -j`\n"
    msg += f"To see status: `{conf.CMD_PREFIX}werewolf -s`\n"
    msg += f"To start: `{conf.CMD_PREFIX}werewolf -start [-restricted]`\n"
    msg += f"To set mode: `{conf.CMD_PREFIX}werewolf -mode <mode>`\n"
    msg += f"To see modes: `{conf.CMD_PREFIX}werewolf -mode`"
    return await event.reply(msg)
