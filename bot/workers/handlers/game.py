import asyncio
import random

from bot import sudo_btn_lock
from bot.config import bot, conf
from bot.games.register import register_for_a_game
from bot.games.werewolf.defaults import DETECTIVE_REVEAL_CHANCE, MAX_PLAYERS
from bot.games.werewolf.game import Game
from bot.games.werewolf.logic import game_loop
from bot.games.werewolf.roles import gamemodes
from bot.utils.log_utils import logger
from bot.utils.msg_utils import get_args
from bot.utils.sudo_button_utils import active_poll_dict, create_sudo_button


async def werewolf_handler(event, args, client):
    """
    Werewolf Game Handler

    Commands:
    -j : Join game
    -l : Leave game
    -s : Game status
    --start : Start game
    --mode <mode> : Set game mode
    -r : Enable restricted mode
    """
    cmd = event.text.split()[0].removeprefix(conf.CMD_PREFIX).casefold()
    if cmd in ("lynch", "id", "shoot"):
        game = bot.current_games_dict.get("werewolf", {}).get(event.chat.id)
        if game and not isinstance(game, dict) and not game.waiting:
            return await handle_game_command(game, event, cmd)
        return
    if not args:
        return await were_info(event, args, client)
    arg, args = get_args(
        "--mode",
        ["-j", "store_true"],
        ["-l", "store_true"],
        ["-s", "store_true"],
        ["--start", "store_true"],
        ["-r", "store_true"],
        to_parse=args,
        get_unknown=True,
    )
    res = register_for_a_game("werewolf", event)
    if not res:
        return
    if res == "started":
        game = bot.current_games_dict.get("werewolf", {}).get(event.chat.id)
        if arg.s:
            return await game.status(event)
        return await event.reply("A game is already in progress in this chat.")

    current_games = bot.current_games_dict.setdefault("werewolf", {})
    game = current_games.get(event.chat.id)

    if arg.j:
        if not game or isinstance(game, dict):
            game = Game(event)
            if arg.r:
                game.restricted = True
            current_games[event.chat.id] = game
            asyncio.create_task(auto_start_manager(event, game))
            return await event.reply("Game lobby created! Use `-j` to join.")
        return await game.join(event)
    if arg.l:
        if not game or isinstance(game, dict):
            return await event.reply("No game found in chat! Use `-j` to start & join.")
        return await game.leave(event)

    if arg.r and game and not isinstance(game, dict):
        game.restricted = True
        await event.reply("will restrict dead/non-players")

    if arg.s:
        if not game or isinstance(game, dict):
            return await event.reply("No game in progress in this chat.")
        return await game.status(event)

    if arg.start:
        if not game or isinstance(game, dict):
            return await event.reply("No game lobby created. Use `-j` to start one.")
        if not game.waiting:
            return await event.reply("Game is already in progress.")

        if arg.r:
            game.restricted = True

        return await start_game(event, game)

    if arg.mode:
        if game and not isinstance(game, dict) and not game.waiting:
            return await event.reply("Cannot change mode after game started.")

        mode_name = arg.mode.casefold()
        if mode_name == "all":
            msg = "*Available Gamemodes:*\n"
            for m, data in gamemodes.items():
                if not data.get("roles"):
                    continue
                msg += f"- *{m}* ({data['min_players']}-{data['max_players']} players): {data['description']}\n"
            return await event.reply(msg)

        # modes without roles aren't implemented and would end instantly
        if not gamemodes.get(mode_name, {}).get("roles"):
            return await event.reply(f"Mode *{mode_name}* not found.")

        if not game or isinstance(game, dict):
            game = Game(event, mode=mode_name)
            if arg.r:
                game.restricted = True
            current_games[event.chat.id] = game
            asyncio.create_task(auto_start_manager(event, game))
            return await event.reply(
                f"Game lobby created with mode *{mode_name}*! Use `-j` to join."
            )
        else:
            game.requested_mode = mode_name
            return await event.reply(f"Mode set to *{mode_name}*.")


async def start_game(event, game):
    """Validates the lobby, assigns roles and starts the game loop."""
    game.set_each_role_numbers_and_pool()
    if game.total_players < game.min_players:
        return await event.reply(
            f"Not enough players for mode *{game.mode}*! Need at least {game.min_players}."
        )
    max_players = gamemodes[game.mode].get("max_players", MAX_PLAYERS)
    if game.total_players > max_players:
        return await event.reply(
            f"Too many players for mode *{game.mode}*! Maximum is {max_players}."
        )
    # assign before the task starts so the game can't be started twice
    game.assign_roles()
    game.activity.set()  # wake the lobby manager so it can clean up
    asyncio.create_task(game_loop(game))
    return await event.reply(
        f"Game starting with mode *{game.mode}*! Restricted: {game.restricted}. Check your PMs for roles."
    )


def find_target(game, target_str):
    return game.get_player_by_id(target_str.lstrip("#")) or next(
        (p for p in game.players_alive_list if target_str.lower() in p.name.lower()),
        None,
    )


async def handle_game_command(game, event, cmd_type):
    player = game.get_player_by_user_id(event.from_user.id)
    if not player or not player.is_alive:
        return

    args = event.text.split(maxsplit=1)
    target_str = args[1].strip() if len(args) > 1 else None

    if cmd_type == "lynch":
        if not game.day:
            return await event.reply("You can only lynch during the day!")
        if not target_str:
            return await event.reply(f"Usage: {conf.CMD_PREFIX}lynch <id or name>")

        target = find_target(game, target_str)
        if not target or not target.is_alive:
            return await event.reply("Invalid target.")

        player.vote = target.user_id
        await event.reply(f"You voted to lynch {target.name}!")

    elif cmd_type == "id":
        if not game.day:
            return await event.reply("You can only use id during the day!")
        if player.role != "detective":
            return
        if game.detective_acted:
            return await event.reply("You have already used your ability today.")
        if not target_str:
            return await event.reply(f"Usage: {conf.CMD_PREFIX}id <id or name>")

        target = find_target(game, target_str)
        if not target or not target.is_alive:
            return await event.reply("Invalid target.")

        game.detective_acted = True
        await game.send_pm(
            player,
            f"Your investigation reveals that {target.name} is a *{target.role}*.",
        )
        if random.random() < DETECTIVE_REVEAL_CHANCE:
            await game.wolfchat(
                f"The detective has been revealed! It is {player.name}."
            )

    elif cmd_type == "shoot":
        if not game.day:
            return await event.reply("You can only shoot during the day!")
        if "gunner" not in player.templates and "sharpshooter" not in player.templates:
            return
        if player.bullet_count <= 0:
            return await event.reply("You are out of bullets!")
        if not target_str:
            return await event.reply(f"Usage: {conf.CMD_PREFIX}shoot <id or name>")

        target = find_target(game, target_str)
        if not target or not target.is_alive:
            return await event.reply("Invalid target.")

        player.bullet_count -= 1
        await game.send_lobby(
            f"*{player.name}* takes out a gun and shoots at *{target.name}*!"
        )

        hit_chance = 1.0 if "sharpshooter" in player.templates else 0.8
        # wolves intentionally miss other wolves
        if player.actual_team == "wolf" and target.actual_team == "wolf":
            hit_chance = 0
        if random.random() < hit_chance:
            if target.actual_team == "wolf":
                extra = await game.kill(target, "shot")
                await game.send_lobby(
                    f"Bullseye! *{target.name}* was a *{target.role}* and has been shot dead.\n{extra}"
                )
            else:
                if random.random() < 0.5:
                    extra = await game.kill(target, "shot")
                    await game.send_lobby(
                        f"Oh no! *{target.name}* was an innocent *{target.role}* but has been shot dead.\n{extra}"
                    )
                else:
                    target.is_injured = True
                    await game.send_lobby(
                        f"*{target.name}* has been injured by the shot!"
                    )
        else:
            await game.send_lobby(f"The shot missed!")


async def werewolf_restriction_handler(client, event):
    if not event.chat.is_group:
        return
    current_games = bot.current_games_dict.get("werewolf", {})
    game = current_games.get(event.chat.id)
    if not game or isinstance(game, dict) or game.waiting or not game.restricted:
        return
    if game.ended or not game.players:
        return
    player = game.get_player_by_user_id(event.from_user.id)
    if not player or not player.is_alive:
        try:
            await event.delete()
        except Exception:
            pass


async def were_info(event, args, client):
    msg = "*Werewolf Game*\n\n"
    msg += f"To join/create: `{conf.CMD_PREFIX}werewolf -j`\n"
    msg += f"To leave: `{conf.CMD_PREFIX}werewolf -l`\n"
    msg += f"To see status: `{conf.CMD_PREFIX}werewolf -s`\n"
    msg += f"To start: `{conf.CMD_PREFIX}werewolf --start [-r]`\n"
    msg += f"To set mode: `{conf.CMD_PREFIX}werewolf --mode <mode>`\n"
    msg += f"To see modes: `{conf.CMD_PREFIX}werewolf --mode all`"
    return await event.reply(msg)


async def auto_start_manager(event, game):
    options = {
        "join": ("Join",),
        "leave": ("Leave",),
    }

    async def btn_callback(event, poll_msg_key):
        selected = await bot.client.decrypt_poll_vote(event.message)
        if not (poll_info := active_poll_dict.get(poll_msg_key.ID)):
            return
        actions = [poll_info.get(s.hex()) for s in selected.selectedOptions]
        if "join" in actions:
            return await game.join(event, notify=True)
        elif "leave" in actions:
            return await game.leave(event, notify=True)

    msg = None
    try:
        _, msg = await create_sudo_button(
            name="Werewolf Game Lobby",
            options=options,
            chat_jid=event.chat.jid,
            user_id="",
            selectable=1,
            callback=btn_callback,
        )
        # start once nobody has joined/left for a while
        while game.waiting and len(game.player_ids) < MAX_PLAYERS:
            if not game.player_ids:  # everyone left
                return
            try:
                await asyncio.wait_for(game.activity.wait(), timeout=180)
            except asyncio.TimeoutError:
                break
            game.activity.clear()
        if not game.waiting:  # Already started elsewhere
            return
        if not game.player_ids:
            return
        await start_game(event, game)
        if game.waiting:  # couldn't start
            game.close()
            await event.reply("The game lobby has been closed.")
    except Exception:
        await logger(Exception)
    finally:
        if msg:
            async with sudo_btn_lock:
                active_poll_dict.pop(msg.ID, None)
            try:
                await bot.client.revoke_message(
                    event.chat.jid, bot.client.me.JID, msg.ID
                )
            except Exception:
                pass
