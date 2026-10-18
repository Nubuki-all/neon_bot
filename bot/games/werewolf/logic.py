import asyncio
import random
from datetime import datetime

from bot import sudo_btn_lock
from bot.config import conf
from bot.utils.log_utils import logger
from bot.utils.sudo_button_utils import (
    active_poll_dict,
    create_sudo_button,
    wait_for_button_response,
)

from .defaults import (
    COMMANDS_FOR_ROLE,
    SHAMAN_TOTEMS,
    WOLF_SHAMAN_TOTEMS,
    WOLFCHAT_ROLES,
    lang,
)


def win_condition(game):
    teams = {"village": 0, "wolf": 0, "neutral": 0}
    players_alive = game.players_alive_list
    if not players_alive:
        return "no win", "Everyone died. The town sits abandoned, collecting dust.", []

    def get_plurals(item, sgl="", plr="s", invert=False):
        if invert:
            return "" if item > 1 else "s"
        return plr if item > 1 else sgl

    living_monster_num = len([p for p in players_alive if p.role == "monster"])
    living_cultists_minions = [
        p for p in players_alive if p.role in ["cultist", "minion"]
    ]
    living_sk_num = len([p for p in players_alive if p.role == "serial killer"])

    for player in players_alive:
        # injured villagers can't vote so they don't count against the wolves
        if player.is_injured and player.actual_team != "wolf":
            continue
        if (player.role in ["cultist", "minion"]) and game.mode != "evilvillage":
            teams["village"] += 1
        else:
            teams[player.actual_team] += 1

    winners, win_team, win_lore = [], "", ""
    all_lovers = (len(players_alive) > 1) and all(
        p.loves and any(game.get_player_by_user_id(l_id).is_alive for l_id in p.loves)
        for p in players_alive
    )

    if all_lovers:
        win_team, win_lore = (
            "lovers",
            "Game over! The remaining villagers through their inseparable love for each other have agreed to stop all of this senseless violence and coexist in peace forever more. All remaining players win.",
        )
    elif len(
        [p for p in players_alive if p.role == "succubus" or "entranced" in p.other]
    ) == len(players_alive):
        win_team = "succubi"
        win_lore = "Game over! The succub{} completely enthralled the village, making them officers in an ever-growing army set on spreading their control and influence throughout the entire world.".format(
            "i"
            if len([p for p in game.players.values() if p.original_role == "succubus"])
            > 1
            else "us"
        )
    elif len(
        [p for p in players_alive if p.role == "piper" or "charmed" in p.other]
    ) == len(players_alive):
        win_team = "pipers"
        p_num = len([p for p in game.players.values() if p.original_role == "piper"])
        win_lore = "Game over! Everyone has fallen victim to the charms of the piper{0}. The piper{0} lead{1} the villagers away from the village, never to return...".format(
            get_plurals(p_num), get_plurals(p_num, invert=True)
        )
    elif living_sk_num >= len(players_alive) / 2:
        if living_monster_num > 0:
            win_team, win_lore = (
                "monster",
                "Game over! The serial killer{0} stabbed all those in the village, except the monster{1}, causing the monster{1} to win.".format(
                    get_plurals(living_sk_num), get_plurals(living_monster_num)
                ),
            )
        else:
            win_team = "serial killers"
            win_lore = "Game over! The serial killer{0} stabbed all those in the village! The serial killer{0} walk{1} off, in the hope to successfully do the same at another location.".format(
                get_plurals(living_sk_num), get_plurals(living_sk_num, invert=True)
            )
    elif teams["village"] + teams["neutral"] <= teams["wolf"] and not (
        game.mode == "evilvillage" and teams["village"]
    ):
        if game.mode == "evilvillage":
            if not teams["village"]:
                if living_monster_num > 0:
                    win_team = "monster"
                    win_lore = "Game over! All the villagers are dead! As the cultists rejoice, they get destroyed by the monster{0}, causing the monster{0} to win.".format(
                        get_plurals(living_monster_num)
                    )
                elif not (len(players_alive) - len(living_cultists_minions)):
                    win_team = "no win"
                    win_lore = "Game over! All the villagers are dead, but the cult needed to sacrifice the wolves to accomplish that. The cult disperses shortly thereafter, and nobody wins."
                else:
                    win_team = "wolf"
                    win_lore = "Game over! All the villagers are dead! The cultists rejoice with their wolf buddies and start plotting to take over the next village."
        elif living_monster_num > 0:
            win_team = "monster"
            win_lore = "Game over! The number of uninjured villagers is equal or less than the number of living wolves! The wolves overpower the villagers but then get destroyed by the monster{0}, causing the monster{0} to win.".format(
                get_plurals(living_monster_num)
            )
        else:
            win_team = "wolf"
            win_lore = "The number of uninjured villagers is equal or less than the number of living wolves! The wolves overpower the remaining villagers and devour them whole."
    elif (
        len(
            [
                p
                for p in players_alive
                if p.team == "wolf" and p.role not in ["cultist", "minion"]
            ]
        )
        == 0
        and living_sk_num == 0
    ):
        if living_monster_num > 0:
            win_team = "monster"
            win_lore = "Game over! All the wolves are dead! As the villagers start preparing the BBQ, the monster{0} quickly kill{1} the remaining villagers, causing the monster{0} to win.".format(
                get_plurals(living_monster_num),
                get_plurals(living_monster_num, invert=True),
            )
        else:
            if (
                len(living_cultists_minions) == teams["wolf"]
                and game.mode == "evilvillage"
            ):
                win_team = "village"
                win_lore = "Game over! All the wolves are dead! The villagers round up the remaining cultists, hang them, and live happily ever after."
            else:
                win_team = "village"
                win_lore = "All the wolves are dead! The surviving villagers gather the bodies of the dead wolves, roast them, and have a BBQ in celebration."
    elif teams["village"] >= teams["wolf"] and game.mode == "evilvillage":
        if living_monster_num > 0:
            win_team = "monster"
            win_lore = "Game over! The number of uninjured cultists is equal or less than the number of living villagers! as the villagers regain control over the village, the monster{0} quickly kill{1} the remaining villagers, causing the monster{0} to win.".format(
                get_plurals(living_monster_num),
                get_plurals(living_monster_num, invert=True),
            )
        elif not living_cultists_minions:
            win_team = "village"
            win_lore = "Game over! All the cultists are dead! The now-exposed wolves are captured and killed by the remaining villagers. A BBQ party commences shortly thereafter."
        else:
            win_team = "village"
            win_lore = "Game over! The number of uninjured cultists is equal or less than the number of living villagers! They manage to regain control of the village and dispose of the remaining cultists."
    else:
        return None

    for p in game.players.values():
        role, other, is_winner = p.role, p.other, False
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
        elif role == "executioner" and "won" in other:
            is_winner = True
        elif role == "vengeful ghost" and not p.is_alive:
            swore_against = getattr(p, "vengeance_against", None)
            if swore_against and win_team != swore_against:
                is_winner = True
        if not is_winner and p.loves:
            if win_team == "lovers" or all(
                game.get_player_by_user_id(l_id).is_alive for l_id in p.loves
            ):
                is_winner = True
        if is_winner:
            winners.append(p.user_id)
        if (win_team != "succubi" and "entranced" in other) or (
            win_team != "pipers" and "charmed" in other
        ):
            if p.user_id in winners:
                winners.remove(p.user_id)
    return win_team, win_lore, winners


async def game_loop(game):
    try:
        await game.send_lobby(
            f"Welcome to Werewolf! Using the *{game.mode}* game mode with *{game.total_players}* players."
        )
        for p in game.players.values():
            if p.role == "executioner":
                villagers = [
                    v
                    for v in game.players.values()
                    if v.team == "villager" and v.user_id != p.user_id
                ]
                if villagers:
                    target = random.choice(villagers)
                    p.execution_target = target.user_id
                    await game.send_pm(p, f"Your target for lynch is *{target.name}*.")
        wolfchat = [p for p in game.players.values() if p.role in WOLFCHAT_ROLES]
        for p in game.players.values():
            msg = f"Your role is *{p.role}*.\n\n{p.description}"
            if p.templates:
                msg += f"\n\nTemplates: {', '.join(p.templates)}"
            if p in wolfchat and len(wolfchat) > 1:
                msg += "\n\nYour team: " + ", ".join(
                    f"{w.name} ({w.role})" for w in wolfchat if w is not p
                )
            await game.send_pm(p, msg)
        await night_phase(game, is_night_zero=True)
        while not game.ended:
            if win := win_condition(game):
                await end_game(game, win)
                break
            if game.night:
                await day_phase(game)
            else:
                await night_phase(game)
    except Exception:
        await logger(Exception)
        await game.send_lobby("*An error occurred, the game has been stopped.*")
    finally:
        game.close()


def has_night_action(game, p, is_night_zero):
    if "hexed" in p.other:
        return False
    if is_night_zero:
        return p.role in ["matchmaker", "clone"]
    if p.role == "vengeful ghost":
        return not p.is_alive and bool(getattr(p, "vengeance_against", None))
    if not p.is_alive:
        return False
    if p.role == "hunter" and "hunted" in p.other:
        return False
    # the detective acts during the day
    return any(
        p.role in roles_ for cmd, roles_ in COMMANDS_FOR_ROLE.items() if cmd != "id"
    )


async def night_phase(game, is_night_zero=False):
    game.night, game.day = True, False
    if not is_night_zero:
        game.night_num += 1
    game.night_start_time = datetime.now()
    await game.send_lobby("It is now *nighttime*.")
    for p in game.players.values():
        p.target = ""
        p.remove_other("guarded")
        for t in SHAMAN_TOTEMS + WOLF_SHAMAN_TOTEMS:
            p.remove_other(t)
    for p in game.players_alive_list:
        if (
            p.role in ["shaman", "wolf shaman", "crazed shaman"]
            and "hexed" not in p.other
        ):
            if p.role == "shaman":
                p.totem = random.choice(SHAMAN_TOTEMS)
            elif p.role == "wolf shaman":
                p.totem = random.choice(WOLF_SHAMAN_TOTEMS)
            else:
                p.totem = random.choice(SHAMAN_TOTEMS + WOLF_SHAMAN_TOTEMS)
            await game.send_pm(
                p, f"Your totem tonight is: *{p.totem.replace('_', ' ')}*."
            )
    tasks = [
        asyncio.create_task(request_night_action(game, p, is_night_zero))
        for p in game.players.values()
        if has_night_action(game, p, is_night_zero)
    ]
    if tasks:
        _, pending = await asyncio.wait(tasks, timeout=game.night_timeout + 5)
        # don't let late answers leak into the next phase
        for task in pending:
            task.cancel()
    if is_night_zero:
        await process_night_zero(game)
    else:
        await process_night(game)
    await game.check_traitor()


async def request_night_action(game, player, is_night_zero):
    options = {}
    if player.role == "matchmaker":
        for p in game.players.values():
            options[p.user_id] = [f"{p.name} (#{p.id})"]
    elif player.role == "clone":
        for p in game.players.values():
            if p.user_id != player.user_id:
                options[p.user_id] = [f"{p.name} (#{p.id})"]
    elif player.role == "piper":
        for p in game.players_alive_list:
            if p.user_id != player.user_id and "charmed" not in p.other:
                options[p.user_id] = [f"{p.name} (#{p.id})"]
    elif player.role == "vengeful ghost":
        against = getattr(player, "vengeance_against", "wolf")
        for p in game.players_alive_list:
            if p.actual_team == against:
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
    if not options:
        return
    if player.role in [
        "hunter",
        "serial killer",
        "harlot",
        "succubus",
        "guardian angel",
        "bodyguard",
        "piper",
    ]:
        options["pass"] = ["Pass"]
    prompt = f"Choose target ({player.role}):"
    if player.role == "matchmaker":
        prompt = "Select 2 lovers, then Confirm:"
    elif player.role == "piper":
        prompt = "Select up to 2 to charm, then Confirm:"
    selectable, conf_btn = 1, None
    if player.role in ["matchmaker", "piper"]:
        # every vote change is a new poll update; wait for an explicit confirm
        conf_btn = "Confirm"
        options["confirm"] = [conf_btn]
        selectable = 3
    msg_id = None
    try:
        _, msg_ = await create_sudo_button(
            prompt,
            options,
            player.jid,
            player.user_id,
            selectable=selectable,
            conf_btn=conf_btn,
        )
        msg_id = msg_.ID
        response = await wait_for_button_response(msg_id, timeout=game.night_timeout)
        response = [r for r in (response or []) if r and r != "confirm"]
        if not response:
            return
        if "pass" in response:
            player.target = "pass"
            return await game.send_pm(player, "Action: Passed.")
        if player.role == "matchmaker" and len(response) != 2:
            return await game.send_pm(player, "You must select exactly 2 lovers.")
        response = response[:2]
        player.target = ",".join(response)
        target_names = ", ".join(
            game.get_player_by_user_id(uid).name for uid in response
        )
        await game.send_pm(player, f"Target set to: {target_names}")
        if is_night_zero or not player.is_alive:
            return
        target = game.get_player_by_user_id(response[0])
        if player.role == "seer":
            await game.send_pm(
                player,
                f"Your vision reveals that {target.name} is a *{target.display_role}*.",
            )
        elif player.role == "oracle":
            await game.send_pm(
                player,
                f"Your vision reveals that {target.name} is {'a wolf' if target.actual_team == 'wolf' else 'not a wolf'}.",
            )
        elif player.role == "augur":
            aura = (
                "red"
                if target.actual_team == "wolf"
                else ("grey" if target.actual_team == "neutral" else "blue")
            )
            await game.send_pm(player, f"{target.name} has a {aura} aura.")
        elif player.role == "sorcerer":
            is_info = (
                "an info role"
                if target.role in ["seer", "oracle", "augur"]
                else "not an info role"
            )
            await game.send_pm(
                player, f"Your observation reveals that {target.name} is {is_info}."
            )
    except asyncio.CancelledError:
        raise
    except Exception:
        await logger(Exception)
    finally:
        if msg_id:
            async with sudo_btn_lock:
                active_poll_dict.pop(msg_id, None)


async def process_night_zero(game):
    for p in game.players.values():
        if p.role == "matchmaker" and p.target:
            uids = p.target.split(",")
            if len(uids) == 2:
                p1, p2 = game.get_player_by_user_id(
                    uids[0]
                ), game.get_player_by_user_id(uids[1])
                if p1 and p2:
                    p1.loves.append(p2.user_id)
                    p2.loves.append(p1.user_id)
                    await game.send_pm(
                        p1,
                        f"You are in love with *{p2.name}*. If they die, you will commit suicide.",
                    )
                    await game.send_pm(
                        p2,
                        f"You are in love with *{p1.name}*. If they die, you will commit suicide.",
                    )
        elif p.role == "clone" and p.target:
            p.cloning_target = p.target
            await game.send_pm(
                p,
                f"You are cloning *{game.get_player_by_user_id(p.target).name}*. If they die, you take their role.",
            )


def _target(game, p):
    """Returns the player targeted by p, if any."""
    if not p.target or p.target == "pass":
        return None
    return game.get_player_by_user_id(p.target.split(",")[0])


async def process_night(game):
    killed = []
    # hexes only last for the night after they were cast
    for p in game.players.values():
        p.remove_other("hexed")
    for p in game.players_alive_list:
        if p.role == "hag" and (target := _target(game, p)):
            target.add_other("hexed")
        if p.role in ["shaman", "wolf shaman", "crazed shaman"] and (
            target := _target(game, p)
        ):
            target.add_other(p.totem)
            if p.totem == "silence_totem":
                target.add_other("hexed")
    for p in game.players_alive_list:
        if p.role == "werecrow" and (target := _target(game, p)):
            status = "out of bed" if target.target else "in bed"
            await game.send_pm(
                p,
                f"Your observation reveals that {target.name} was {status} last night.",
            )
    protected_uids = []
    for p in game.players_alive_list:
        if p.role in ["guardian angel", "bodyguard"] and (target := _target(game, p)):
            protected_uids.append(target.user_id)
        if "protection_totem" in p.other:
            protected_uids.append(p.user_id)
    wolf_targets = {}
    wolves = [
        p
        for p in game.players_alive_list
        if p.team == "wolf" and p.role in COMMANDS_FOR_ROLE["kill"]
    ]
    for w in wolves:
        if target := _target(game, w):
            wolf_targets[target.user_id] = wolf_targets.get(target.user_id, 0) + 1
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
        if p.role in ["serial killer", "hunter"] and (target := _target(game, p)):
            if p.role == "hunter":
                p.add_other("hunted")
            if target.user_id not in protected_uids:
                killed.append(target.user_id)
        if "death_totem" in p.other:
            killed.append(p.user_id)
    for p in game.players_alive_list:
        if p.role == "harlot" and (target := _target(game, p)):
            if target.actual_team == "wolf" or target.user_id in killed:
                killed.append(p.user_id)
    for p in game.players_alive_list:
        if p.role == "succubus" and (target := _target(game, p)):
            if "bishop" not in target.templates:
                target.add_other("entranced")
        if p.role == "piper" and p.target and p.target != "pass":
            for t_id in p.target.split(","):
                if target := game.get_player_by_user_id(t_id):
                    target.add_other("charmed")
    for p in game.players.values():
        if not p.is_alive and p.role == "vengeful ghost" and (target := _target(game, p)):
            killed.append(target.user_id)
    killed_msg = ""
    for uid in dict.fromkeys(killed):
        p = game.get_player_by_user_id(uid)
        if p and p.is_alive:
            if p.role == "lycan" or "lycanthropy_totem" in p.other:
                p.role, p.team = "wolf", "wolf"
                await game.send_pm(p, "HOOOOOOOOOWL. You have become... a wolf!")
                continue
            killed_msg += f"The dead body of *{p.name}*, a *{p.role}*, was found.\n"
            killed_msg += await game.kill(p, "night")
    if not killed_msg:
        killed_msg = random.choice(lang["nokills"]) + "\n"
    await game.send_lobby(
        f"Night lasted long enough. The villagers wake up and search the village.\n\n{killed_msg}"
    )


async def day_phase(game):
    game.night, game.day, game.detective_acted = False, True, False
    game.day_start_time = datetime.now()
    for p in game.players.values():
        p.vote = ""
    await game.send_lobby(
        f"It is now *daytime*. Use `{conf.CMD_PREFIX}lynch <player>` to vote to lynch."
    )
    elapsed, warned = 0, False
    # end the day early once everyone alive has voted
    while elapsed < game.day_timeout:
        if win_condition(game):
            return
        if all(p.vote for p in game.players_alive_list):
            break
        if not warned and elapsed >= game.day_warning:
            warned = True
            await game.send_lobby(
                f"*{game.day_timeout - elapsed}s* left to vote before the day ends!"
            )
        await asyncio.sleep(5)
        elapsed += 5
    vote_counts = {}
    for p in game.players_alive_list:
        v_weight = 1
        if "impatience_totem" in p.other:
            v_weight += 1
        if "pacifism_totem" in p.other:
            v_weight -= 1
        target = game.get_player_by_user_id(p.vote)
        if (p.vote == "abstain" or (target and target.is_alive)) and v_weight > 0:
            vote_counts[p.vote] = vote_counts.get(p.vote, 0) + v_weight
    if not vote_counts:
        return await game.send_lobby("Not enough votes were cast to lynch a player.")
    top = max(vote_counts.values())
    leaders = [uid for uid, count in vote_counts.items() if count == top]
    if len(leaders) > 1:
        return await game.send_lobby("The vote was tied, nobody was lynched today.")
    lynched_uid = leaders[0]
    if lynched_uid == "abstain":
        return await game.send_lobby("The village has agreed to not lynch anyone today.")
    p = game.get_player_by_user_id(lynched_uid)
    if "mayor" in p.templates and "revealed_mayor" not in p.other:
        p.add_other("revealed_mayor")
        return await game.send_lobby(
            f"While being dragged to the gallows, *{p.name}* reveals that they are the *mayor*. The village agrees to let them live for now."
        )
    p.is_lynched = True
    p.add_other("lynched")
    msg = random.choice(lang["lynched"]).format(p.name, p.role)
    extra = await game.kill(p, "lynch")
    await game.send_lobby(f"{msg}\n{extra}" if extra else msg)
    for exe in game.players_alive_list:
        if exe.role == "executioner" and exe.execution_target == p.user_id:
            exe.add_other("won")
    if p.role == "fool":
        await end_game(
            game,
            (
                "fool",
                "The fool has been lynched, causing them to win!",
                [p.user_id],
            ),
        )
    await game.check_traitor()


async def end_game(game, win_data):
    game.ended = True
    win_team, win_lore, winners_ids = win_data
    msg = f"*GAME OVER!*\n\n{win_lore}\n\n*Winners:*\n"
    for uid in winners_ids:
        p = game.get_player_by_user_id(uid)
        msg += f"- {p.name} ({p.role})\n"
    if not winners_ids:
        msg += "- Nobody\n"
    msg += "\n*Final player list:*\n"
    for p in game.players.values():
        msg += f"- {p.name}: {p.role} ({'Alive' if p.is_alive else 'Dead'})\n"
    await game.send_lobby(msg)
    game.close()
