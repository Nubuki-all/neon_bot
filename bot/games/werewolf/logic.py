import asyncio
import random
from datetime import datetime

from bot.config import bot
from bot.utils.sudo_button_utils import create_sudo_button, wait_for_button_response

from .defaults import (
    ACTUAL_WOLVES,
    COMMANDS_FOR_ROLE,
    SHAMAN_TOTEMS,
    WOLF_SHAMAN_TOTEMS,
    lang,
)


def win_condition(game):
    teams = {"village": 0, "wolf": 0, "neutral": 0}
    players_alive = game.players_alive_list

    if not players_alive:
        return "no win", "Everyone died. The town sits abandoned, collecting dust.", []

    for player in players_alive:
        if player.is_injured:
            if (
                player.role in ACTUAL_WOLVES
                and player.role not in ["cultist", "minion"]
                and "entranced" not in player.other
            ):
                continue

        if (player.role in ["cultist", "minion"]) and game.mode != "evilvillage":
            teams["village"] += 1
        else:
            teams[player.team] += 1

    winners = []
    win_team = ""
    win_lore = ""

    # Lovers win
    all_lovers = True
    for p in players_alive:
        if not p.loves:
            all_lovers = False
            break
        if not any(game.get_player_by_user_id(l_id).is_alive for l_id in p.loves):
            all_lovers = False
            break
    if all_lovers and len(players_alive) > 1:
        return (
            "lovers",
            "Game over! The remaining villagers through their inseparable love for each other have agreed to stop all of this senseless violence and coexist in peace forever more. All remaining players win.",
            [p.user_id for p in players_alive],
        )

    # Succubus win
    succubi_alive = [p for p in players_alive if p.role == "succubus"]
    entranced_alive = [p for p in players_alive if "entranced" in p.other]
    if succubi_alive and (len(succubi_alive) + len(entranced_alive)) == len(
        players_alive
    ):
        return (
            "succubi",
            "Game over! The succubi completely enthralled the village.",
            [p.user_id for p in players_alive],
        )

    # Piper win
    pipers_alive = [p for p in players_alive if p.role == "piper"]
    charmed_alive = [p for p in players_alive if "charmed" in p.other]
    if pipers_alive and (len(pipers_alive) + len(charmed_alive)) == len(players_alive):
        return (
            "pipers",
            "Game over! Everyone has fallen victim to the charms of the piper.",
            [p.user_id for p in players_alive],
        )

    # Serial Killer win
    sk_alive = [p for p in players_alive if p.role == "serial killer"]
    if sk_alive and len(sk_alive) >= len(players_alive) / 2:
        return (
            "serial killers",
            "Game over! The serial killer stabbed all those in the village!",
            [p.user_id for p in sk_alive],
        )

    monster_alive = [p for p in players_alive if p.role == "monster"]

    if teams["village"] + teams["neutral"] <= teams["wolf"] and not (
        game.mode == "evilvillage" and teams["village"]
    ):
        if monster_alive:
            win_team = "monster"
            win_lore = "The wolves overpower the villagers but then get destroyed by the monster!"
        else:
            win_team = "wolf"
            win_lore = (
                "The wolves overpower the remaining villagers and devour them whole."
            )
    elif teams["wolf"] == 0 and not sk_alive:
        if monster_alive:
            win_team = "monster"
            win_lore = "All the wolves are dead! As the villagers start preparing the BBQ, the monster quickly kills them."
        else:
            win_team = "village"
            win_lore = (
                "All the wolves are dead! The surviving villagers celebrate with a BBQ."
            )
    else:
        return None

    for p in game.players.values():
        role = p.role
        other = p.other
        is_winner = False
        if p.actual_team == win_team:
            is_winner = True
        elif role == "lycan" and win_team == "village":
            is_winner = True
        elif role == "amnesiac" and win_team == "village":
            is_winner = True
        elif role == "piper" and win_team == "pipers":
            is_winner = True
        elif (role == "succubus" or "entranced" in other) and win_team == "succubi":
            is_winner = True
        elif role == "jester" and "lynched" in other:
            is_winner = True
        elif role == "monster" and win_team == "monster":
            is_winner = True
        elif role == "serial killer" and win_team == "serial killers":
            is_winner = True
        if not is_winner and p.loves:
            if all(game.get_player_by_user_id(l_id).is_alive for l_id in p.loves):
                is_winner = True
        if is_winner:
            winners.append(p.user_id)
        if (win_team != "succubi" and "entranced" in other) or "charmed" in other:
            if p.user_id in winners:
                winners.remove(p.user_id)
    return win_team, win_lore, winners


async def game_loop(game):
    await game.send_lobby(
        f"The game of Werewolf (Mode: {game.mode}) is starting with {game.total_players} players!"
    )
    game.assign_roles()
    for p in game.players.values():
        msg = f"Your role is *{p.role}*.\n\n{p.description}"
        if p.templates:
            msg += f"\n\nTemplates: {', '.join(p.templates)}"
        try:
            await bot.client.send_message(p.user_id, msg)
        except Exception:
            pass
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
    for p in game.players_alive_list:
        if p.role == "shaman":
            p.totem = random.choice(SHAMAN_TOTEMS)
            await bot.client.send_message(
                p.user_id, f"You have a *{p.totem.replace('_', ' ')}* tonight."
            )
        elif p.role == "wolf shaman":
            p.totem = random.choice(WOLF_SHAMAN_TOTEMS)
            await bot.client.send_message(
                p.user_id, f"You have a *{p.totem.replace('_', ' ')}* tonight."
            )
        elif p.role == "crazed shaman":
            p.totem = random.choice(SHAMAN_TOTEMS + WOLF_SHAMAN_TOTEMS)
            await bot.client.send_message(
                p.user_id, f"You have a random totem tonight."
            )
    tasks = []
    for p in game.players_alive_list:
        should_act = False
        if is_night_zero:
            if p.role in ["matchmaker", "clone"]:
                should_act = True
        else:
            if any(
                p.role in COMMANDS_FOR_ROLE.get(cmd, [])
                for cmd in [
                    "kill",
                    "see",
                    "give",
                    "guard",
                    "observe",
                    "visit",
                    "hex",
                    "curse",
                    "charm",
                ]
            ):
                should_act = True
        if should_act:
            tasks.append(request_night_action(game, p, is_night_zero))
    if tasks:
        await asyncio.wait(
            [asyncio.create_task(t) for t in tasks], timeout=game.night_timeout
        )
    if is_night_zero:
        await process_night_zero(game)
    else:
        await process_night(game)
    await game.check_traitor()


async def request_night_action(game, player, is_night_zero):
    options = {}
    if player.role == "matchmaker":
        for p in game.players_alive_list:
            options[p.user_id] = [f"{p.name} (#{p.id})"]
    elif player.role == "clone":
        for p in game.players_alive_list:
            if p.user_id != player.user_id:
                options[p.user_id] = [f"{p.name} (#{p.id})"]
    elif player.role == "piper":
        for p in game.players_alive_list:
            if p.user_id != player.user_id and "charmed" not in p.other:
                options[p.user_id] = [f"{p.name} (#{p.id})"]
    else:
        for p in game.players_alive_list:
            if p.user_id == player.user_id and player.role not in [
                "harlot",
                "succubus",
                "guardian angel",
                "bodyguard",
                "shaman",
                "wolf shaman",
                "crazed shaman",
            ]:
                continue
            options[p.user_id] = [f"{p.name} (#{p.id})"]
    if player.role in [
        "hunter",
        "serial killer",
        "harlot",
        "succubus",
        "guardian angel",
        "bodyguard",
        "piper",
    ]:
        options["pass"] = ["Pass / Stay Home / None"]
    prompt = f"Choose your target for tonight ({player.role}):"
    if player.role == "matchmaker":
        prompt = "Choose TWO players to be lovers (Select 2):"
    elif player.role == "piper":
        prompt = "Choose up to TWO players to charm (Select 2):"
    try:
        selectable = 2 if player.role in ["matchmaker", "piper"] else 1
        _, msg_id = await create_sudo_button(
            prompt, options, player.user_id, player.user_id, selectable=selectable
        )
        response = await wait_for_button_response(msg_id)
        if response:
            player.target = ",".join(response)
            if "pass" in response:
                await bot.client.send_message(player.user_id, "Action: Passed.")
                return
            target_names = ", ".join(
                [
                    game.get_player_by_user_id(uid).name if uid != "pass" else "Pass"
                    for uid in response
                ]
            )
            await bot.client.send_message(
                player.user_id, f"Target set to: {target_names}"
            )
            if not is_night_zero:
                if player.role in ["seer", "oracle", "augur"]:
                    target = game.get_player_by_user_id(response[0])
                    if player.role == "seer":
                        await bot.client.send_message(
                            player.user_id,
                            f"Your vision reveals that {target.name} is a *{target.display_role}*.",
                        )
                    elif player.role == "oracle":
                        is_wolf = "wolf" if target.team == "wolf" else "not a wolf"
                        await bot.client.send_message(
                            player.user_id,
                            f"Your vision reveals that {target.name} is {is_wolf}.",
                        )
                    elif player.role == "augur":
                        aura = (
                            "red"
                            if target.team == "wolf"
                            else ("grey" if target.team == "neutral" else "blue")
                        )
                        await bot.client.send_message(
                            player.user_id,
                            f"Your vision reveals that {target.name} has a {aura} aura.",
                        )
                elif player.role == "sorcerer":
                    target = game.get_player_by_user_id(response[0])
                    is_info = (
                        "an info role"
                        if target.role in ["seer", "oracle", "augur"]
                        else "not an info role"
                    )
                    await bot.client.send_message(
                        player.user_id,
                        f"Your observation reveals that {target.name} is {is_info}.",
                    )
    except Exception:
        pass


async def process_night_zero(game):
    for p in game.players_alive_list:
        if p.role == "matchmaker" and p.target:
            uids = p.target.split(",")
            if len(uids) == 2:
                p1, p2 = game.get_player_by_user_id(
                    uids[0]
                ), game.get_player_by_user_id(uids[1])
                if p1 and p2:
                    p1.loves, p2.loves = [p2.user_id], [p1.user_id]
                    await bot.client.send_message(
                        p1.user_id, f"You are now in love with {p2.name}!"
                    )
                    await bot.client.send_message(
                        p2.user_id, f"You are now in love with {p1.name}!"
                    )
        elif p.role == "clone" and p.target:
            p.cloning_target = p.target
            await bot.client.send_message(
                p.user_id,
                f"You are cloning {game.get_player_by_user_id(p.target).name}.",
            )


async def process_night(game):
    killed = []
    for p in game.players_alive_list:
        if p.role == "hag" and p.target:
            target = game.get_player_by_user_id(p.target)
            if target:
                target.add_other("hexed")
    for p in game.players_alive_list:
        if p.role in ["shaman", "wolf shaman", "crazed shaman"] and p.target:
            target = game.get_player_by_user_id(p.target)
            if target:
                target.add_other(p.totem)
                if p.totem == "silence_totem":
                    target.add_other("hexed")
    for p in game.players_alive_list:
        if p.role == "werecrow" and p.target:
            target = game.get_player_by_user_id(p.target)
            status = "out of bed" if target.target else "in bed"
            await bot.client.send_message(
                p.user_id,
                f"Your observation reveals that {target.name} was {status} last night.",
            )
    protected_uids = []
    for p in game.players_alive_list:
        if (
            p.role in ["guardian angel", "bodyguard"]
            and p.target
            and p.target != "pass"
        ):
            protected_uids.append(p.target)
        if "protection_totem" in p.other:
            protected_uids.append(p.user_id)
    wolf_targets = {}
    wolves = [
        p
        for p in game.players_alive_list
        if p.team == "wolf" and p.role in COMMANDS_FOR_ROLE["kill"]
    ]
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
    for p in game.players_alive_list:
        if p.role == "serial killer" and p.target and p.target != "pass":
            if p.target not in protected_uids:
                killed.append(p.target)
    for p in game.players_alive_list:
        if "death_totem" in p.other:
            killed.append(p.user_id)
    for p in game.players_alive_list:
        if p.role == "harlot" and p.target and p.target != "pass":
            target = game.get_player_by_user_id(p.target)
            if target.team == "wolf" or target.user_id in killed:
                killed.append(p.user_id)
    for p in game.players_alive_list:
        if p.role == "succubus" and p.target and p.target != "pass":
            target = game.get_player_by_user_id(p.target)
            if "bishop" not in target.templates:
                target.add_other("entranced")
                await bot.client.send_message(
                    target.user_id, "You have been entranced by a succubus!"
                )
    for p in game.players_alive_list:
        if p.role == "piper" and p.target and p.target != "pass":
            for t_id in p.target.split(","):
                target = game.get_player_by_user_id(t_id)
                if target:
                    target.add_other("charmed")
    killed_msg = ""
    for uid in set(killed):
        p = game.get_player_by_user_id(uid)
        if p and p.is_alive:
            if p.role == "lycan" or "lycanthropy_totem" in p.other:
                p.role = "wolf"
                p.team = "wolf"
                await bot.client.send_message(
                    p.user_id,
                    "You were attacked but turned into a *wolf* instead of dying!",
                )
                continue
            p.is_alive = False
            killed_msg += f"The dead body of *{p.name}*, a *{p.role}*, was found.\n"
            if p.role == "mad scientist":
                idx = game.player_ids.index(p.user_id)
                for offset in [-1, 1]:
                    neighbor_id = game.player_ids[(idx + offset) % len(game.player_ids)]
                    neighbor = game.get_player_by_user_id(neighbor_id)
                    if neighbor and neighbor.is_alive:
                        neighbor.is_alive = False
                        killed_msg += f"The mad scientist's chemicals killed *{
                            neighbor.name}*!\n"
            if p.role == "time lord":
                game.day_timeout //= 2
                game.night_timeout //= 2
                await game.send_lobby(
                    "The Time Lord has fallen! Time begins to speed up..."
                )
            for cloner in game.players_alive_list:
                if cloner.role == "clone" and cloner.cloning_target == p.user_id:
                    cloner.role = p.role
                    cloner.team = p.team
                    await bot.client.send_message(
                        cloner.user_id,
                        f"Your clone target died. You are now a *{cloner.role}*!",
                    )
            if p.loves:
                for l_id in p.loves:
                    lover = game.get_player_by_user_id(l_id)
                    if lover and lover.is_alive:
                        lover.is_alive = False
                        killed_msg += f"*{
                            lover.name}* committed suicide out of grief for their lover.\n"
    if not killed_msg:
        killed_msg = random.choice(lang["nokills"])
    await game.send_lobby(f"Night {game.night_num} has ended.\n\n{killed_msg}")


async def day_phase(game):
    game.night, game.day = False, True
    game.day_start_time, game.detective_acted = datetime.now(), False
    for p in game.players.values():
        p.vote = ""
    await game.send_lobby(
        f"It is now *Day {game.night_num}*. Discussion is open. Use `.lynch <id>` to vote."
    )
    await asyncio.sleep(game.day_timeout)
    vote_counts = {}
    for p in game.players_alive_list:
        v_weight = 1
        if "impatience_totem" in p.other:
            v_weight += 1
        if "pacifism_totem" in p.other:
            v_weight -= 1
        if p.vote:
            vote_counts[p.vote] = vote_counts.get(p.vote, 0) + v_weight
    if vote_counts:
        lynched_uid = max(vote_counts, key=vote_counts.get)
        if lynched_uid != "abstain":
            p = game.get_player_by_user_id(lynched_uid)
            if p:
                if "mayor" in p.templates and "revealed_mayor" not in p.other:
                    p.add_other("revealed_mayor")
                    await game.send_lobby(
                        f"While being dragged to the gallows, *{p.name}* reveals that they are the *mayor*! The village agrees to let them live for now."
                    )
                else:
                    p.is_alive, p.is_lynched = False, True
                    p.add_other("lynched")
                    await game.send_lobby(
                        f"The village has lynched *{p.name}*. They were a *{p.role}*."
                    )
                    if p.role == "fool":
                        await end_game(
                            game,
                            ("fool", "The fool has won by being lynched!", [p.user_id]),
                        )
                        return
        else:
            await game.send_lobby("The village has decided to abstain today.")
    else:
        await game.send_lobby("No one was lynched today.")


async def end_game(game, win_data):
    win_team, win_lore, winners_ids = win_data
    msg = f"*GAME OVER!*\n\n{win_lore}\n\n*Winners:*\n"
    for uid in winners_ids:
        p = game.get_player_by_user_id(uid)
        if p:
            msg += f"- {p.name} ({p.role})\n"
    msg += "\n*Full player list:*\n"
    for p in game.players.values():
        status = "Alive" if p.is_alive else "Dead"
        msg += f"- {p.name} (#{p.id}): {p.role} ({status})\n"
    await game.send_lobby(msg)
    bot.current_games_dict.get("werewolf", {}).pop(game.chat_id, None)
    if game.game_id in bot.current_games_dict.get("werewolf_ids", []):
        bot.current_games_dict["werewolf_ids"].remove(game.game_id)
