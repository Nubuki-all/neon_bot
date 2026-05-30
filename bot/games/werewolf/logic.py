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
    if not players_alive: return "no win", "Everyone died. The town sits abandoned, collecting dust.", []

    for player in players_alive:
        if player.is_injured and player.team == "wolf" and player.role not in ["cultist", "minion"] and "entranced" not in player.other: continue
        if (player.role in ["cultist", "minion"]) and game.mode != "evilvillage": teams["village"] += 1
        else: teams[player.team] += 1

    winners, win_team, win_lore = [], "", ""
    all_lovers = (len(players_alive) > 1) and all(p.loves and any(game.get_player_by_user_id(l_id).is_alive for l_id in p.loves) for p in players_alive)

    if all_lovers:
        win_team = "lovers"
        win_lore = "Game over! The remaining villagers through their inseparable love for each other have agreed to stop all of this senseless violence and coexist in peace forever more. All remaining players win."
    elif len([p for p in players_alive if p.role == "succubus" or "entranced" in p.other]) == len(players_alive):
        win_team = "succubi"
        win_lore = "Game over! The succubi completely enthralled the village, making them officers in an ever-growing army set on spreading their control and influence throughout the entire world."
    elif len([p for p in players_alive if p.role == "piper" or "charmed" in p.other]) == len(players_alive):
        win_team = "pipers"
        win_lore = "Game over! Everyone has fallen victim to the charms of the piper. The piper leads the villagers away from the village, never to return..."
    elif len([p for p in players_alive if p.role == "serial killer"]) >= len(players_alive) / 2:
        if any(p.role == "monster" for p in players_alive):
            win_team = "monster"
            win_lore = "Game over! The serial killer stabbed all those in the village, except the monster, causing the monster to win."
        else:
            win_team = "serial killers"
            win_lore = "Game over! The serial killer stabbed all those in the village! The serial killer walks off, in the hope to successfully do the same at another location."
    elif teams["village"] + teams["neutral"] <= teams["wolf"] and not (game.mode == "evilvillage" and teams["village"]):
        if game.mode == "evilvillage":
            if not teams["village"]:
                if any(p.role == "monster" for p in players_alive):
                    win_team = "monster"
                    win_lore = "Game over! All the villagers are dead! As the cultists rejoice, they get destroyed by the monster, causing the monster to win."
                elif not (len(players_alive) - len([p for p in players_alive if p.role in ["cultist", "minion"]])):
                    win_team = "no win"
                    win_lore = "Game over! All the villagers are dead, but the cult needed to sacrifice the wolves to accomplish that. The cult disperses shortly thereafter, and nobody wins."
                else:
                    win_team = "wolf"
                    win_lore = "Game over! All the villagers are dead! The cultists rejoice with their wolf buddies and start plotting to take over the next village."
        elif any(p.role == "monster" for p in players_alive):
            win_team = "monster"
            win_lore = "Game over! The number of uninjured villagers is equal or less than the number of living wolves! The wolves overpower the villagers but then get destroyed by the monster, causing the monster to win."
        else:
            win_team = "wolf"
            win_lore = "The number of uninjured villagers is equal or less than the number of living wolves! The wolves overpower the remaining villagers and devour them whole."
    elif len([p for p in players_alive if p.team == "wolf" or p.role == "serial killer" or p.role == "monster"]) == 0:
        # Simplification: if monster is dead, villagers win if wolves/SK are dead
        if game.mode == "evilvillage":
             win_team = "village"
             win_lore = "Game over! All the wolves are dead! The villagers round up the remaining cultists, hang them, and live happily ever after."
        else:
             win_team = "village"
             win_lore = "All the wolves are dead! The surviving villagers gather the bodies of the dead wolves, roast them, and have a BBQ in celebration."
    elif teams["wolf"] == 0 and any(p.role == "monster" for p in players_alive):
         win_team = "monster"
         win_lore = "Game over! All the wolves are dead! As the villagers start preparing the BBQ, the monster quickly kills the remaining villagers, causing the monster to win."
    else: return None

    for p in game.players.values():
        role, other, is_winner = p.role, p.other, False
        if p.actual_team == win_team: is_winner = True
        elif role == "lycan" and win_team == "village": is_winner = True
        elif role == "amnesiac" and win_team == "village": is_winner = True
        elif role == "piper" and win_team == "pipers": is_winner = True
        elif (role == "succubus" or "entranced" in other) and win_team == "succubi": is_winner = True
        elif role == "jester" and "lynched" in other: is_winner = True
        elif role == "monster" and win_team == "monster": is_winner = True
        elif role == "serial killer" and win_team == "serial killers": is_winner = True
        elif role == "executioner" and "won" in other: is_winner = True
        elif role == "vengeful ghost" and not p.is_alive:
             swore_against = getattr(p, "vengeance_against", None)
             if swore_against and win_team != swore_against: is_winner = True
        if not is_winner and p.loves:
             if win_team == "lovers" or all(game.get_player_by_user_id(l_id).is_alive for l_id in p.loves): is_winner = True
        if is_winner: winners.append(p.user_id)
        if (win_team != "succubi" and "entranced" in other) or (win_team != "pipers" and "charmed" in other):
             if p.user_id in winners: winners.remove(p.user_id)
    return win_team, win_lore, winners


async def game_loop(game):
    await game.send_lobby(f"Welcome to Werewolf! Using the *{game.mode}* game mode with *{game.total_players}* players.")
    game.assign_roles()
    for p in game.players.values():
         if p.role == "executioner":
              villagers = [v for v in game.players.values() if v.team == "villager" and v.user_id != p.user_id]
              if villagers:
                   target = random.choice(villagers); p.execution_target = target.user_id
                   await bot.client.send_message(p.user_id, f"Your target for lynch is *{target.name}*.")
    for p in game.players.values():
        msg = f"Your role is *{p.role}*.\n\n{p.description}"
        if p.templates: msg += f"\n\nTemplates: {', '.join(p.templates)}"
        try: await bot.client.send_message(p.user_id, msg)
        except Exception: pass
    await night_phase(game, is_night_zero=True)
    game.day = True
    while True:
        win = win_condition(game)
        if win: await end_game(game, win); break
        if not game.day: await night_phase(game)
        else: await day_phase(game)
        game.day = not game.day


async def night_phase(game, is_night_zero=False):
    game.night, game.day = True, False
    if not is_night_zero: game.night_num += 1
    game.night_start_time = datetime.now()
    await game.send_lobby(f"It is now **nighttime**.")
    for p in game.players.values():
        p.target = ""
        p.remove_other("hexed"); p.remove_other("guarded")
        for t in SHAMAN_TOTEMS + WOLF_SHAMAN_TOTEMS: p.remove_other(t)
    for p in game.players_alive_list:
        if p.role in ["shaman", "wolf shaman", "crazed shaman"] and "hexed" not in p.other:
            if p.role == "shaman": p.totem = random.choice(SHAMAN_TOTEMS)
            elif p.role == "wolf shaman": p.totem = random.choice(WOLF_SHAMAN_TOTEMS)
            else: p.totem = random.choice(SHAMAN_TOTEMS + WOLF_SHAMAN_TOTEMS)
            await bot.client.send_message(p.user_id, f"Your totem tonight is: **{p.totem.replace('_', ' ')}**.")
    tasks = []
    for p in (game.players_alive_list if not is_night_zero else game.players.values()):
        if "hexed" in p.other: continue
        if (is_night_zero and p.role in ["matchmaker", "clone"]) or (not is_night_zero and any(p.role in COMMANDS_FOR_ROLE.get(cmd, []) for cmd in ["kill", "see", "give", "guard", "observe", "visit", "hex", "curse", "charm"])):
            tasks.append(request_night_action(game, p, is_night_zero))
        elif not is_night_zero and p.role == "vengeful ghost" and not p.is_alive and getattr(p, "vengeance_against", None):
             tasks.append(request_night_action(game, p, False))
    if tasks: await asyncio.wait([asyncio.create_task(t) for t in tasks], timeout=game.night_timeout)
    if is_night_zero: await process_night_zero(game)
    else: await process_night(game)
    await game.check_traitor()


async def request_night_action(game, player, is_night_zero):
    options = {}
    if player.role == "matchmaker":
        for p in game.players.values(): options[p.user_id] = [f"{p.name} (#{p.id})"]
    elif player.role == "clone":
        for p in game.players.values():
             if p.user_id != player.user_id: options[p.user_id] = [f"{p.name} (#{p.id})"]
    elif player.role == "piper":
        for p in game.players_alive_list:
             if p.user_id != player.user_id and "charmed" not in p.other: options[p.user_id] = [f"{p.name} (#{p.id})"]
    elif player.role == "vengeful ghost":
         against = getattr(player, "vengeance_against", "wolf")
         for p in game.players_alive_list:
              if p.actual_team == against: options[p.user_id] = [f"{p.name} (#{p.id})"]
    else:
        for p in game.players_alive_list:
            if p.user_id == player.user_id and player.role not in ["harlot", "succubus", "guardian angel", "bodyguard", "shaman", "wolf shaman", "crazed shaman"]: continue
            options[p.user_id] = [f"{p.name} (#{p.id})"]
    if player.role in ["hunter", "serial killer", "harlot", "succubus", "guardian angel", "bodyguard", "piper"]: options["pass"] = ["Pass"]
    prompt = f"Choose target ({player.role}):"
    if player.role == "matchmaker": prompt = "Select 2 lovers:"
    elif player.role == "piper": prompt = "Select up to 2 charmed:"
    try:
        selectable = 2 if player.role in ["matchmaker", "piper"] else 1
        _, msg_id = await create_sudo_button(prompt, options, player.user_id, player.user_id, selectable=selectable)
        response = await wait_for_button_response(msg_id)
        if response:
            player.target = ",".join(response)
            if "pass" in response: await bot.client.send_message(player.user_id, "Action: Passed."); return
            target_names = ", ".join([game.get_player_by_user_id(uid).name for uid in response if uid != "pass"])
            await bot.client.send_message(player.user_id, f"Target set to: {target_names}")
            if not is_night_zero and player.is_alive:
                if player.role in ["seer", "oracle", "augur"]:
                    target = game.get_player_by_user_id(response[0])
                    if player.role == "seer": await bot.client.send_message(player.user_id, f"Your vision reveals that {target.name} is a **{target.display_role}**.")
                    elif player.role == "oracle": await bot.client.send_message(player.user_id, f"Your vision reveals that {target.name} is {'a wolf' if target.team == 'wolf' else 'not a wolf'}.")
                    elif player.role == "augur":
                        aura = "red" if target.team == "wolf" else ("grey" if target.team == "neutral" else "blue")
                        await bot.client.send_message(player.user_id, f"Your vision reveals that {target.name} has a {aura} aura.")
                elif player.role == "sorcerer":
                    target = game.get_player_by_user_id(response[0]); is_info = "an info role" if target.role in ["seer", "oracle", "augur"] else "not an info role"
                    await bot.client.send_message(player.user_id, f"Your observation reveals that {target.name} is {is_info}.")
    except Exception: pass


async def process_night_zero(game):
     for p in game.players.values():
          if p.role == "matchmaker" and p.target:
               uids = p.target.split(",")
               if len(uids) == 2:
                    p1, p2 = game.get_player_by_user_id(uids[0]), game.get_player_by_user_id(uids[1])
                    if p1 and p2:
                         p1.loves, p2.loves = [p2.user_id], [p1.user_id]
                         await bot.client.send_message(p1.user_id, f"You are in love with **{p2.name}**. If they die, you will commit suicide."); await bot.client.send_message(p2.user_id, f"You are in love with **{p1.name}**. If they die, you will commit suicide.")
          elif p.role == "clone" and p.target:
               p.cloning_target = p.target; await bot.client.send_message(p.user_id, f"You are cloning **{game.get_player_by_user_id(p.target).name}**. If they die, you take their role.")

async def process_night(game):
    killed = []
    for p in game.players_alive_list:
         if p.role == "hag" and p.target: game.get_player_by_user_id(p.target).add_other("hexed")
         if p.role in ["shaman", "wolf shaman", "crazed shaman"] and p.target:
              target = game.get_player_by_user_id(p.target); target.add_other(p.totem)
              if p.totem == "silence_totem": target.add_other("hexed")
    for p in game.players_alive_list:
        if p.role == "werecrow" and p.target:
            status = "out of bed" if game.get_player_by_user_id(p.target).target else "in bed"
            await bot.client.send_message(p.user_id, f"Your observation reveals that {game.get_player_by_user_id(p.target).name} was {status} last night.")
    protected_uids = []
    for p in game.players_alive_list:
        if p.role in ["guardian angel", "bodyguard"] and p.target and p.target != "pass": protected_uids.append(p.target)
        if "protection_totem" in p.other: protected_uids.append(p.user_id)
    wolf_targets = {}
    wolves = [p for p in game.players_alive_list if p.team == "wolf" and p.role in COMMANDS_FOR_ROLE["kill"]]
    for w in wolves:
        if w.target and w.target != "pass": wolf_targets[w.target] = wolf_targets.get(w.target, 0) + 1
    if wolf_targets:
        target_uid = max(wolf_targets, key=wolf_targets.get)
        if target_uid in protected_uids:
            for p in game.players_alive_list:
                if p.role == "bodyguard" and p.target == target_uid: killed.append(p.user_id); break
        else: killed.append(target_uid)
    for p in game.players_alive_list:
        if p.role == "serial killer" and p.target and p.target != "pass":
            if p.target not in protected_uids: killed.append(p.target)
        if "death_totem" in p.other: killed.append(p.user_id)
        if p.role == "harlot" and p.target and p.target != "pass":
            target = game.get_player_by_user_id(p.target)
            if target.team == "wolf" or target.user_id in killed: killed.append(p.user_id)
    for p in game.players_alive_list:
         if p.role == "succubus" and p.target and p.target != "pass":
              target = game.get_player_by_user_id(p.target)
              if "bishop" not in target.templates: target.add_other("entranced")
         if p.role == "piper" and p.target and p.target != "pass":
              for t_id in p.target.split(","): game.get_player_by_user_id(t_id).add_other("charmed")
    for p in game.players.values():
         if not p.is_alive and p.role == "vengeful ghost" and p.target: killed.append(p.target)
    killed_msg = ""
    for uid in set(killed):
        p = game.get_player_by_user_id(uid)
        if p and p.is_alive:
            if p.role == "lycan" or "lycanthropy_totem" in p.other:
                 p.role, p.team = "wolf", "wolf"; await bot.client.send_message(p.user_id, "HOOOOOOOOOWL. You have become... a wolf!"); continue
            p.is_alive = False; killed_msg += f"The dead body of **{p.name}**, a **{p.role}**, was found.\n"
            if p.role == "vengeful ghost": p.vengeance_against = "wolf" # simplified
            for cloner in game.players_alive_list:
                 if cloner.role == "clone" and cloner.cloning_target == p.user_id:
                      cloner.role, cloner.team = p.role, p.team; await bot.client.send_message(cloner.user_id, f"Your clone target died. You are now a **{cloner.role}**!")
            if p.loves:
                for l_id in p.loves:
                    lover = game.get_player_by_user_id(l_id)
                    if lover and lover.is_alive: lover.is_alive = False; killed_msg += f"**{lover.name}** committed suicide out of grief for their lover.\n"
    if not killed_msg: killed_msg = random.choice(lang["nokills"]) + "\n"
    await game.send_lobby(f"Night lasted long enough. The villagers wake up and search the village.\n\n{killed_msg}")


async def day_phase(game):
    game.night, game.day, game.detective_acted = False, True, False
    for p in game.players.values(): p.vote = ""
    await game.send_lobby(f"It is now **daytime**. Use `{bot.conf.CMD_PREFIX}lynch <player>` to vote to lynch.")
    await asyncio.sleep(game.day_timeout)
    vote_counts = {}
    for p in game.players_alive_list:
        v_weight = 1
        if "impatience_totem" in p.other: v_weight += 1
        if "pacifism_totem" in p.other: v_weight -= 1
        if p.vote: vote_counts[p.vote] = vote_counts.get(p.vote, 0) + v_weight
    if vote_counts:
        lynched_uid = max(vote_counts, key=vote_counts.get)
        if lynched_uid != "abstain":
            p = game.get_player_by_user_id(lynched_uid)
            if p:
                if "mayor" in p.templates and "revealed_mayor" not in p.other:
                     p.add_other("revealed_mayor"); await game.send_lobby(f"While being dragged to the gallows, **{p.name}** reveals that they are the **mayor**. The village agrees to let them live for now.")
                else:
                    p.is_alive, p.is_lynched = False, True; p.add_other("lynched")
                    await game.send_lobby(random.choice(lang["lynched"]).format(p.name, p.role))
                    for exe in game.players_alive_list:
                         if exe.role == "executioner" and exe.execution_target == p.user_id: exe.add_other("won")
                    if p.role == "fool": await end_game(game, ("fool", "The fool has been lynched, causing them to win!", [p.user_id])); return
        else: await game.send_lobby("The village has agreed to not lynch anyone today.")
    else: await game.send_lobby("Not enough votes were cast to lynch a player.")


async def end_game(game, win_data):
    win_team, win_lore, winners_ids = win_data
    msg = f"**GAME OVER!**\n\n{win_lore}\n\n**Winners:**\n"
    for uid in winners_ids:
        p = game.get_player_by_user_id(uid); msg += f"- {p.name} ({p.role})\n"
    msg += "\n**Final player list:**\n"
    for p in game.players.values(): msg += f"- {p.name}: {p.role} ({'Alive' if p.is_alive else 'Dead'})\n"
    await game.send_lobby(msg)
    bot.current_games_dict.get("werewolf", {}).pop(game.chat_id, None)
    if game.game_id in bot.current_games_dict.get("werewolf_ids", []): bot.current_games_dict["werewolf_ids"].remove(game.game_id)
