import random
import asyncio
from datetime import datetime

from bot.config import bot
from bot.utils.sudo_button_utils import create_sudo_button, wait_for_button_response, active_poll_dict

from .defaults import ACTUAL_WOLVES, COMMANDS_FOR_ROLE, lang, SHAMAN_TOTEMS, WOLF_SHAMAN_TOTEMS, DETECTIVE_REVEAL_CHANCE
from .roles import roles, gamemodes


def win_condition(game):
    teams = {"village": 0, "wolf": 0, "neutral": 0}
    players_alive = game.players_alive_list

    if not players_alive:
        return "no win", "Everyone died. The town sits abandoned, collecting dust.", []

    for player in players_alive:
        if player.is_injured:
            if player.role in ACTUAL_WOLVES and player.role not in ["cultist", "minion"] and "entranced" not in player.other_data:
                continue

        if (player.role in ["cultist", "minion"]) and game.mode != "evilvillage":
            teams["village"] += 1
        else:
            teams[player.team] += 1

    winners = []
    win_team = ""
    win_lore = ""

    # Lovers win
    lovers_alive = [p for p in players_alive if p.loves and game.get_player_by_user_id(p.loves).is_alive]
    if len(lovers_alive) == len(players_alive) and len(players_alive) > 0:
        return "lovers", "Game over! The remaining villagers through their inseparable love for each other have agreed to stop all of this senseless violence and coexist in peace forever more. All remaining players win.", [p.user_id for p in players_alive]

    # Succubus win
    succubi_alive = [p for p in players_alive if p.role == "succubus"]
    entranced_alive = [p for p in players_alive if "entranced" in p.other_data]
    if succubi_alive and (len(succubi_alive) + len(entranced_alive)) == len(players_alive):
        return "succubi", "Game over! The succubi completely enthralled the village.", [p.user_id for p in players_alive]

    monster_alive = [p for p in players_alive if p.role == "monster"]

    # Wolf win condition
    if teams["village"] + teams["neutral"] <= teams["wolf"]:
        if monster_alive:
            win_team = "monster"
            win_lore = "The wolves overpower the villagers but then get destroyed by the monster!"
        else:
            win_team = "wolf"
            win_lore = "The wolves overpower the remaining villagers and devour them whole."
    # Village win condition
    elif teams["wolf"] == 0:
        if monster_alive:
            win_team = "monster"
            win_lore = "All the wolves are dead! As the villagers start preparing the BBQ, the monster quickly kills them."
        else:
            win_team = "village"
            win_lore = "All the wolves are dead! The surviving villagers celebrate with a BBQ."
    else:
        return None

    for p in game.players.values():
        if win_team == "village":
            if p.team == "village" or p.role in ["lycan", "amnesiac"]:
                winners.append(p.user_id)
        elif win_team == "wolf":
            if p.team == "wolf" or "entranced" in p.other_data:
                winners.append(p.user_id)
        elif win_team == "monster":
            if p.role == "monster":
                winners.append(p.user_id)

    return win_team, win_lore, winners


async def game_loop(game):
    await game.send_lobby(f"The game of Werewolf (Mode: {game.mode}) is starting with {game.total_players} players!")

    game.assign_roles()

    for p in game.players.values():
        msg = f"Your role is *{p.role}*.\n\n{p.description}"
        if p.templates:
            msg += f"\n\nTemplates: {', '.join(p.templates)}"
        try:
            await bot.client.send_message(p.user_id, msg)
        except Exception:
            pass

    # Night 0
    await night_phase(game, is_night_zero=True)
    game.day = True

    while True:
        win = win_condition(game)
        if win:
            await end_game(game, win)
            break

        if not game.day:
            await night_phase(game)
        else:
            await day_phase(game)

        game.day = not game.day


async def night_phase(game, is_night_zero=False):
    game.night = True
    game.day = False
    if not is_night_zero:
        game.night_num += 1
    game.night_start_time = datetime.now()

    phase_name = "Night 0" if is_night_zero else f"Night {game.night_num}"
    await game.send_lobby(f"It is now *{phase_name}*. Villagers, go to sleep...")

    for p in game.players.values():
        p.target = ""
        p.remove_other("hexed")
        p.remove_other("guarded")
        for t in SHAMAN_TOTEMS + WOLF_SHAMAN_TOTEMS:
            p.remove_other(t)

    # Shaman totem generation
    for p in game.players_alive_list:
        if p.role == "shaman":
            p.totem = random.choice(SHAMAN_TOTEMS)
            await bot.client.send_message(p.user_id, f"You have a *{p.totem.replace('_', ' ')}* tonight.")
        elif p.role == "wolf shaman":
            p.totem = random.choice(WOLF_SHAMAN_TOTEMS)
            await bot.client.send_message(p.user_id, f"You have a *{p.totem.replace('_', ' ')}* tonight.")
        elif p.role == "crazed shaman":
            p.totem = random.choice(SHAMAN_TOTEMS + WOLF_SHAMAN_TOTEMS)
            await bot.client.send_message(p.user_id, "You have a random totem tonight.")

    tasks = []
    for p in game.players_alive_list:
        should_act = False
        if is_night_zero:
            if p.role in ["matchmaker", "clone"]:
                should_act = True
        else:
            if any(p.role in COMMANDS_FOR_ROLE[cmd] for cmd in ["kill", "see", "give", "guard", "observe", "visit"]):
                should_act = True

        if should_act:
            tasks.append(request_night_action(game, p, is_night_zero))

    if tasks:
        await asyncio.wait([asyncio.create_task(t) for t in tasks], timeout=game.night_timeout)

    if is_night_zero:
        await process_night_zero(game)
    else:
        await process_night(game)


async def request_night_action(game, player, is_night_zero):
    options = {}

    if player.role == "matchmaker":
        for p in game.players_alive_list:
            options[p.user_id] = [f"{p.name} (#{p.id})"]
    elif player.role == "clone":
        for p in game.players_alive_list:
             if p.user_id != player.user_id:
                  options[p.user_id] = [f"{p.name} (#{p.id})"]
    else:
        for p in game.players_alive_list:
            if p.user_id == player.user_id and player.role not in ["harlot", "succubus", "guardian angel", "bodyguard", "shaman", "wolf shaman", "crazed shaman"]:
                continue
            options[p.user_id] = [f"{p.name} (#{p.id})"]

    if player.role in ["hunter", "serial killer", "harlot", "succubus", "guardian angel", "bodyguard", "piper"]:
        options["pass"] = ["Pass / Stay Home / None"]

    prompt = f"Choose your target for tonight ({player.role}):"
    try:
        _, msg_id = await create_sudo_button(prompt, options, player.user_id, player.user_id)
        response = await wait_for_button_response(msg_id)
        if response:
            player.target = response[0]
            if player.target == "pass":
                 await bot.client.send_message(player.user_id, "Action: Passed.")
                 return

            target = game.get_player_by_user_id(player.target)
            await bot.client.send_message(player.user_id, f"Target set to: {target.name}")

            if not is_night_zero:
                if player.role in ["seer", "oracle", "augur"]:
                    if player.role == "seer":
                        await bot.client.send_message(player.user_id, f"Your vision reveals that {target.name} is a *{target.display_role}*.")
                    elif player.role == "oracle":
                        is_wolf = "wolf" if target.team == "wolf" else "not a wolf"
                        await bot.client.send_message(player.user_id, f"Your vision reveals that {target.name} is {is_wolf}.")
                    elif player.role == "augur":
                        aura = "red" if target.team == "wolf" else ("grey" if target.team == "neutral" else "blue")
                        await bot.client.send_message(player.user_id, f"Your vision reveals that {target.name} has a {aura} aura.")
                elif player.role in ["werecrow", "sorcerer"]:
                    if player.role == "werecrow":
                        # We'll check this later in process_night if needed,
                        # or just assume they were out if they have a target.
                        pass
                    elif player.role == "sorcerer":
                         is_info = "an info role" if target.role in ["seer", "oracle", "augur"] else "not an info role"
                         await bot.client.send_message(player.user_id, f"Your observation reveals that {target.name} is {is_info}.")
    except Exception:
        pass


async def process_night_zero(game):
     for p in game.players_alive_list:
          if p.role == "matchmaker" and p.target:
               target = game.get_player_by_user_id(p.target)
               if target:
                    p.loves = target.user_id
                    target.loves = p.user_id
                    await bot.client.send_message(p.user_id, f"You are now in love with {target.name}!")
                    await bot.client.send_message(target.user_id, f"You are now in love with {p.name}!")
          elif p.role == "clone" and p.target:
               p.cloning_target = p.target
               await bot.client.send_message(p.user_id, f"You are cloning {game.get_player_by_user_id(p.target).name}.")

async def process_night(game):
    killed = []

    # Observe for werecrow
    for p in game.players_alive_list:
        if p.role == "werecrow" and p.target and p.target != "pass":
            target = game.get_player_by_user_id(p.target)
            status = "out of bed" if target.target else "in bed"
            await bot.client.send_message(p.user_id, f"Your observation reveals that {target.name} was {status} last night.")

    # Apply totems
    for p in game.players_alive_list:
        if p.role in ["shaman", "wolf shaman", "crazed shaman"] and p.target and p.target != "pass":
            target = game.get_player_by_user_id(p.target)
            if target:
                target.add_other(p.totem)

    # Protections
    protected_uids = []
    for p in game.players_alive_list:
        if p.role in ["guardian angel", "bodyguard"] and p.target and p.target != "pass":
            protected_uids.append(p.target)
        if "protection_totem" in p.other_data:
            protected_uids.append(p.user_id)

    # Wolf kill
    wolf_targets = {}
    wolves = [p for p in game.players_alive_list if p.role in ACTUAL_WOLVES and p.role in COMMANDS_FOR_ROLE["kill"]]
    for w in wolves:
        if w.target and w.target != "pass":
            wolf_targets[w.target] = wolf_targets.get(w.target, 0) + 1

    if wolf_targets:
        target_uid = max(wolf_targets, key=wolf_targets.get)
        if target_uid in protected_uids:
            for p in game.players_alive_list:
                if p.role == "bodyguard" and p.target == target_uid:
                    killed.append(p.user_id)
                    break
        else:
            killed.append(target_uid)

    # Serial killer kill
    for p in game.players_alive_list:
        if p.role == "serial killer" and p.target and p.target != "pass":
            if p.target not in protected_uids:
                killed.append(p.target)

    # Death totem
    for p in game.players_alive_list:
        if "death_totem" in p.other_data:
            killed.append(p.user_id)

    # Harlot check
    for p in game.players_alive_list:
        if p.role == "harlot" and p.target and p.target != "pass":
            target = game.get_player_by_user_id(p.target)
            if target.team == "wolf" or target.user_id in killed:
                killed.append(p.user_id)

    # Apply deaths
    killed_msg = ""
    for uid in set(killed):
        p = game.get_player_by_user_id(uid)
        if p and p.is_alive:
            p.is_dead = True
            killed_msg += f"The dead body of *{p.name}*, a *{p.role}*, was found.\n"

            # Clone check
            for cloner in game.players_alive_list:
                 if cloner.role == "clone" and cloner.cloning_target == p.user_id:
                      cloner.role = p.role
                      cloner.team = p.team
                      await bot.client.send_message(cloner.user_id, f"Your clone target died. You are now a *{cloner.role}*!")

            if p.loves:
                lover = game.get_player_by_user_id(p.loves)
                if lover and lover.is_alive:
                    lover.is_dead = True
                    killed_msg += f"*{lover.name}* committed suicide out of grief for their lover.\n"

    if not killed_msg:
        killed_msg = random.choice(lang["nokills"])

    await game.send_lobby(f"Night {game.night_num} has ended.\n\n{killed_msg}")


async def day_phase(game):
    game.night = False
    game.day = True
    game.day_start_time = datetime.now()
    game.detective_acted = False

    for p in game.players.values():
         p.vote = ""

    await game.send_lobby(f"It is now *Day {game.night_num}*. Discussion is open.")

    # Wait for lynch votes
    await asyncio.sleep(game.day_timeout)

    vote_counts = {}
    for p in game.players_alive_list:
        if p.vote:
            vote_counts[p.vote] = vote_counts.get(p.vote, 0) + 1

    if vote_counts:
        lynched_uid = max(vote_counts, key=vote_counts.get)
        if lynched_uid != "abstain":
            p = game.get_player_by_user_id(lynched_uid)
            if p:
                p.is_dead = True
                p.is_lynched = True
                await game.send_lobby(f"The village has lynched *{p.name}*. They were a *{p.role}*.")
                if p.role == "fool":
                    await end_game(game, ("fool", "The fool has won by being lynched!", [p.user_id]))
                    return
        else:
            await game.send_lobby("The village has decided to abstain today.")
    else:
        await game.send_lobby("No one was lynched today.")


async def end_game(game, win_data):
    win_team, win_lore, winners_ids = win_data
    msg = f"*GAME OVER!*\n\n{win_lore}\n\n"
    msg += "*Winners:*\n"
    for uid in winners_ids:
        p = game.get_player_by_user_id(uid)
        if p:
            msg += f"- {p.name} ({p.role})\n"

    msg += "\n*Full player list:*\n"
    for p in game.players.values():
        msg += f"- {p.name}: {p.role}\n"

    await game.send_lobby(msg)
    bot.current_games_dict.get("werewolf", {}).pop(game.chat_id, None)
    if game.game_id in bot.current_games_dict.get("werewolf_ids", []):
        bot.current_games_dict["werewolf_ids"].remove(game.game_id)
