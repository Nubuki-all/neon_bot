from bot import bot, conf
from bot.utils.log_utils import logger
from bot.utils.msg_utils import tag_users

from .roles import gamemodes, roles


def win_condition(game):
    teams = {"village": 0, "wolf": 0, "neutral": 0}
    injured_wolves = 0
    for player in list(game.players.values()):
        if not player.is_dead:
            if player.is_injured:
                if (
                    player.wolf
                    and not (player.cultist or player.minion)
                    and "entranced" not in player.other
                ):
                    injured_wolves += 1
            else:
                if (player.cultist or player.minion) and game.mode != "evilvillage":
                    teams["village"] += 1
                else:
                    teams[player.team] += 1

    def get_plurals(item, sgl="", plr="s", invert=False):
        if invert:
            return "" if item > 1 else "s"
        return plr if item > 1 else sgl

    winners = []
    win_team = ""
    win_lore = ""
    lovers = []
    mode = gamemodes.get(game.mode)
    current_roles = mode.get("roles")
    players = game.players
    for plr in players:
        if not ((lvr := player.loves) and lvr in players):
            continue
        if plr not in lovers and not player.is_dead:
            lovers.append(plr)
        if lvr not in lovers and not players[lvr].is_dead:
            lovers.append(lvr)

    if game.players_alive == 0:
        win_team = "no win"
        win_lore = "Everyone died. The town sits abandoned, collecting dust."
    elif len(lovers) == game.players_alive:
        win_team = "lovers"
        win_lore = "Game over! The remaining villagers through their inseparable love for each other have agreed to stop all of this senseless violence and coexist in peace forever more. All remaining players win."
    elif (
        "succubus" in current_roles
        and (game.succubus_num + game.entranced_num) == game.players_alive
    ):
        # elif len([player for player in players if not player.is_dead and
        # player.succubus or 'entranced' in player.other) ==
        # game.players_alive:
        win_team = "succubi"
        win_lore = "Game over! The succub{} completely enthralled the village, making them officers in an ever-growing army set on spreading their control and influence throughout the entire world.".format(
            "i" if game._succubus_num > 1 else "us"
        )
    elif (
        "piper" in current_roles
        and (game.piper_num + game.charmed_num) == game.players_alive
    ):
        win_team = "pipers"
        e_str = get_plurals(game._piper_num)
        e_str2 = get_plurals(game._piper_num, invert=True)
        win_lore = "Game over! Everyone has fallen victim to the charms of the piper{0}. The piper{0} lead{1} the villagers away from the village, never to return...".format(
            e_str, e_str2
        )
    elif (
        "serial killer" in current_roles
        and game.serial_killer_num >= game.players_alive / 2
    ):
        if "monster" in current_roles and game.monster_num:
            win_team = "monster"
            e_str = get_plurals(game._serial_killer_num)
            e_str2 = get_plurals(game.monster_num)
            win_lore = "Game over! The serial killer{0} stabbed all those in the village, except the monster{1}, causing the monster{1} to win.".format(
                e_str, e_str2
            )
        else:
            win_team = "serial killers"
            e_str = get_plurals(game._serial_killer_num)
            e_str2 = get_plurals(game._serial_killer_num, invert=True)
            win_lore = "Game over! The serial killer{0} stabbed all those in the village! The serial killer{0} walk{1} off, in the hope to successfully do the same at another location.".format(
                e_str, e_str2
            )
    elif teams["village"] + teams["neutral"] <= teams["wolf"] and not (
        game.mode == "evilvillage" and teams["village"]
    ):
        if game.mode == "evilvillage":
            if not teams["village"]:
                if "monster" in current_roles and game.monster_num:
                    win_team = "monster"
                    win_lore = "Game over! All the villagers are dead! As the cultists rejoice, they get destroyed by the monster{0}, causing the monster{0} to win.".format(
                        get_plurals(game.monster_num)
                    )
                elif not (game.players_alive - (game.cultist_num - game.minion_num)):
                    win_team = "no win"
                    win_lore = "Game over! All the villagers are dead, but the cult needed to sacrifice the wolves to accomplish that. The cult disperses shortly thereafter, and nobody wins."
                else:
                    win_team = "wolf"
                    win_lore = "Game over! All the villagers are dead! The cultists rejoice with their wolf buddies and start plotting to take over the next village."
        elif "monster" in current_roles and game.monster_num:
            win_team = "monster"
            win_lore = "Game over! The number of uninjured villagers is equal or less than the number of living wolves! The wolves overpower the villagers but then get destroyed by the monster{0}, causing the monster{0} to win.".format(
                get_plurals(game.monster_num)
            )
        else:
            win_team = "wolf"
            win_lore = "The number of uninjured villagers is equal or less than the number of living wolves! The wolves overpower the remaining villagers and devour them whole."
    elif (
        len(
            [
                x
                for x in session[1]
                if session[1][x][0]
                and get_role(x, "role") in ACTUAL_WOLVES + ["traitor"]
            ]
        )
        == 0
        and len(
            [
                x
                for x in session[1]
                if session[1][x][0] and get_role(x, "role") == "serial killer"
            ]
        )
        == 0
    ):
        # old version: teams['wolf'] == 0 and injured_wolves == 0:
        if [
            x
            for x in session[1]
            if session[1][x][0] and get_role(x, "role") == "monster"
        ]:
            win_team = "monster"
            win_lore = "Game over! All the wolves are dead! As the villagers start preparing the BBQ, the monster{0} quickly kill{1} the remaining villagers, causing the monster{0} to win.".format(
                (
                    "s"
                    if len(
                        [
                            x
                            for x in session[1]
                            if session[1][x][0] and get_role(x, "role") == "monster"
                        ]
                    )
                    > 1
                    else ""
                ),
                (
                    ""
                    if len(
                        [
                            x
                            for x in session[1]
                            if session[1][x][0] and get_role(x, "role") == "monster"
                        ]
                    )
                    > 1
                    else "s"
                ),
            )
        else:
            if (
                len(
                    [
                        x
                        for x in session[1]
                        if session[1][x][0]
                        and get_role(x, "role") in ["cultist", "minion"]
                    ]
                )
                == teams["wolf"]
                and session[6] == "evilvillage"
            ):
                win_team = "village"
                win_lore = "Game over! All the wolves are dead! The villagers round up the remaining cultists, hang them, and live happily ever after."
            else:
                win_team = "village"
                win_lore = "All the wolves are dead! The surviving villagers gather the bodies of the dead wolves, roast them, and have a BBQ in celebration."
    elif teams["village"] >= teams["wolf"] and session[6] == "evilvillage":
        if [
            x
            for x in session[1]
            if session[1][x][0] and get_role(x, "role") == "monster"
        ]:
            win_team = "monster"
            win_lore = "Game over! The number of uninjured cultists is equal or less than the number of living villagers! as the villagers regain control over the village, the monster{0} quickly kill{1} the remaining villagers, causing the monster{0} to win.".format(
                (
                    "s"
                    if len(
                        [
                            x
                            for x in session[1]
                            if session[1][x][0] and get_role(x, "role") == "monster"
                        ]
                    )
                    > 1
                    else ""
                ),
                (
                    ""
                    if len(
                        [
                            x
                            for x in session[1]
                            if session[1][x][0] and get_role(x, "role") == "monster"
                        ]
                    )
                    > 1
                    else "s"
                ),
            )
        elif not [
            x
            for x in session[1]
            if session[1][x][0] and get_role(x, "role") in ["cultist", "minion"]
        ]:
            win_team = "village"
            win_lore = "Game over! All the cultists are dead! The now-exposed wolves are captured and killed by the remaining villagers. A BBQ party commences shortly thereafter."
        else:
            win_team = "village"
            win_lore = "Game over! The number of uninjured cultists is equal or less than the number of living villagers! They manage to regain control of the village and dispose of the remaining cultists."
    else:
        return None

    for player in session[1]:
        lovers = []
        for n in session[1][player][4]:
            if n.startswith("lover:"):
                lovers.append(n.split(":")[1])
        role = get_role(player, "role")
        if (
            get_role(player, "actualteam") == win_team
            or role == "lycan"
            and win_team == "village"
            or role == "amnesiac"
            and win_team == "village"
            or role == "piper"
            and win_team == "pipers"
            or (role == "succubus" or "entranced" in session[1][player][4])
            and win_team == "succubi"
            or role == "jester"
            and "lynched" in session[1][player][4]
            or role == "executioner"
            and "win" in session[1][player][4]
            or role == "turncoat"
            and (
                "side:villagers" in session[1][player][4]
                and win_team == "village"
                or "side:wolves" in session[1][player][4]
                and win_team == "wolf"
            )
            or not session[1][player][0]
            and role == "vengeful ghost"
            and win_team
            not in [
                x.split(":")[1]
                for x in session[1][player][4]
                if x.startswith("vengeance:")
            ]
            or session[1][player][0]
            and (
                role == "vengeful ghost"
                and win_team == "village"
                or role == "monster"
                and win_team == "monster"
                or role == "serial killer"
                and win_team == "serial killers"
                or role == "clone"
                or [x for x in lovers if session[1][x][0]]
            )
        ):
            winners.append(player)
        if (
            (win_team != "succubi" and "entranced" in session[1][player][4])
            or "charmed" in session[1][player][4]
            or role == "hot potato"
        ) and player in winners:
            winners.remove(player)
    return [win_team, win_lore + "\n\n" + end_game_stats(), winners]


async def game_loop(game, ses=None):
    if ses:
        await bot.client.send_message(
            game.chat_jid,
            "{}\nWelcome to Werewolf, the popular detective/social party game (a theme of Mafia). "
            "Using the *{}* game mode with *{}* players.\nAll players check for PMs from me for instructions. "
            "If you did not receive a pm, please let @{} know.".format(
                tag_users(game.player_ids),
                game.mode,
                conf.OWNER.split()[0],
            ),
        )

    await logger(e="Starting game…")
    game.night = True

    # GAME START
    while win_condition() is None and session[0]:
        if not session[2]:  # NIGHT
            session[3][0] = datetime.now()
            log_msg = ["SUNSET LOG:"]
            num_kills = 1
            for player in session[1]:
                member = client.get_server(WEREWOLF_SERVER).get_member(player)
                role = get_role(player, "role")
                if session[1][player][0]:
                    if role == "shaman":
                        if session[6] == "mudkip":
                            session[1][player][2] = (
                                random.choice(["pestilence_totem", "death_totem"])
                                if not night == 1
                                else "death_totem"
                            )
                        elif session[6] == "aleatoire":
                            # protection (40%), death (20%), retribution (20%),
                            # silence (10%), desperation (5%), pestilence (5%)
                            session[1][player][2] = random.choice(
                                ["protection_totem"] * 8
                                + ["death_totem"] * 4
                                + ["retribution_totem"] * 4
                                + ["silence_totem"] * 2
                                + ["desperation_totem"]
                                + ["pestilence_totem"]
                            )
                        else:
                            session[1][player][2] = random.choice(SHAMAN_TOTEMS)
                        log_msg.append(
                            "{} ({}) HAS {}".format(
                                get_name(player), player, session[1][player][2]
                            )
                        )
                    elif role == "wolf shaman":
                        if session[6] == "mudkip":
                            session[1][player][4].append(
                                "totem:{}".format(
                                    random.choice(
                                        ["protection_totem", "misdirection_totem"]
                                    )
                                )
                            )
                        else:
                            session[1][player][4].append(
                                "totem:{}".format(random.choice(WOLF_SHAMAN_TOTEMS))
                            )
                        log_msg.append(
                            "{} ({}) HAS {}".format(
                                get_name(player),
                                player,
                                [
                                    x.split(":")[1]
                                    for x in session[1][player][4]
                                    if x.startswith("totem:")
                                ].pop(),
                            )
                        )
                    elif role == "crazed shaman":
                        session[1][player][2] = random.choice(list(totems))
                        log_msg.append(
                            "{} ({}) HAS {}".format(
                                get_name(player), player, session[1][player][2]
                            )
                        )
                    elif (
                        role == "hunter" and "hunterbullet" not in session[1][player][4]
                    ):
                        session[1][player][2] = player
                    elif role == "doomsayer":
                        session[1][player][4].append(
                            "doom:{}".format(random.choice(["sick", "lycan", "death"]))
                        )
                    elif role == "piper":
                        session[1][player][4].append("charm")
                elif role == "vengeful ghost":
                    against = "wolf"
                    if [x for x in session[1][player][4] if x.startswith("vengeance:")]:
                        against = [
                            x.split(":")[1]
                            for x in session[1][player][4]
                            if x.startswith("vengeance:")
                        ].pop()
                    if not [
                        x
                        for x in session[1]
                        if session[1][x][0] and get_role(x, "actualteam") == against
                    ]:
                        session[1][player][4].append("notargets")
                if night == 1:
                    await _send_role_info(player)
                else:
                    await _send_role_info(player, sendrole=False)
            await log(1, "\n".join(log_msg))

            session[3][0] = datetime.now()
            await send_lobby("It is now **nighttime**.")
            warn = False
            # NIGHT LOOP
            while win_condition() is None and not session[2] and session[0]:
                end_night = True
                wolf_kill_dict = {}
                num_wolves = 0
                for player in session[1]:
                    role = get_role(player, "role")
                    templates = get_role(player, "templates")
                    if session[1][player][0]:
                        if "silence_totem2" not in session[1][player][4]:
                            if role in [
                                "wolf",
                                "werecrow",
                                "doomsayer",
                                "werekitten",
                                "wolf shaman",
                                "wolf mystic",
                                "hag",
                                "sorcerer",
                                "warlock",
                                "seer",
                                "oracle",
                                "harlot",
                                "hunter",
                                "augur",
                                "guardian angel",
                                "bodyguard",
                                "succubus",
                                "turncoat",
                                "serial killer",
                                "hot potato",
                            ]:
                                end_night = end_night and session[1][player][2]
                                if role == "werecrow":
                                    end_night = (
                                        end_night and "observe" in session[1][player][4]
                                    )
                                elif role == "doomsayer":
                                    end_night = end_night and not [
                                        x
                                        for x in session[1][player][4]
                                        if x.startswith("doom:")
                                    ]
                                elif role == "wolf shaman":
                                    end_night = end_night and not [
                                        x
                                        for x in session[1][player][4]
                                        if x.startswith("totem:")
                                    ]
                            elif role in ["shaman", "crazed shaman"]:
                                end_night = (
                                    end_night and session[1][player][2] in session[1]
                                )
                            elif role == "piper":
                                end_night = (
                                    end_night and "charm" not in session[1][player][4]
                                )
                            elif role == "matchmaker":
                                end_night = (
                                    end_night and "match" not in session[1][player][4]
                                )
                            elif role == "clone":
                                end_night = (
                                    end_night and "clone" not in session[1][player][4]
                                )
                        if "assassin" in templates:
                            end_night = end_night and [
                                x
                                for x in session[1][player][4]
                                if x.startswith("assassinate:")
                            ]
                        if (
                            roles[role][0] == "wolf"
                            and role in COMMANDS_FOR_ROLE["kill"]
                        ):
                            num_wolves += 1
                            num_wolves -= len(
                                [
                                    x
                                    for x in [
                                        y
                                        for y in session[1]
                                        if session[1][y][0]
                                        and roles[get_role(y, "role")][0] == "wolf"
                                        and get_role(y, "role")
                                        in COMMANDS_FOR_ROLE["kill"]
                                    ]
                                    if "silence_totem2" in session[1][x][4]
                                ]
                            )
                            num_kills = session[1][player][4].count("angry") + 1
                            t = session[1][player][2]
                            # if no target then t == '' and that will be a key
                            # in wolf_kill_dict
                            targets = t.split(",")
                            for target in targets:
                                try:
                                    wolf_kill_dict[target] += 1
                                except KeyError:
                                    wolf_kill_dict[target] = 1
                    elif role == "vengeful ghost" and [
                        x for x in session[1][player][4] if x.startswith("vengeance:")
                    ]:
                        end_night = end_night and (
                            session[1][player][2] != ""
                            or "notargets" in session[1][player][4]
                        )
                if num_wolves > 0:
                    end_night = end_night and len(wolf_kill_dict) == num_kills
                    for t in wolf_kill_dict:
                        end_night = end_night and wolf_kill_dict[t] == num_wolves
                        # night will only end if all wolves select same
                        # target(s)
                end_night = (
                    end_night
                    or (datetime.now() - session[3][0]).total_seconds() > night_timeout
                )
                if end_night:
                    session[2] = True
                    # attempted fix for using !time right as night ends
                    session[3][1] = datetime.now()
                if (
                    datetime.now() - session[3][0]
                ).total_seconds() > night_warning and not warn:
                    warn = True
                    await send_lobby(
                        "**A few villagers awake early and notice it is still dark outside. "
                        "The night is almost over and there are still whispers heard in the village.**"
                    )
                await asyncio.sleep(0.1)
            night_elapsed = datetime.now() - session[3][0]
            session[4][0] += night_elapsed

            # BETWEEN NIGHT AND DAY
            # fixes using !time screwing stuff up
            session[3][1] = datetime.now()
            killed_msg = ""
            killed_dict = {}
            for player in session[1]:
                if "blessed" in get_role(player, "templates"):
                    killed_dict[player] = -1
                else:
                    killed_dict[player] = 0
            killed_players = []
            alive_players = [
                x
                for x in session[1]
                if (
                    session[1][x][0]
                    or (
                        get_role(x, "role") == "vengeful ghost"
                        and [a for a in session[1][x][4] if a.startswith("vengeance:")]
                    )
                )
            ]
            log_msg = ["SUNRISE LOG:"]
            if session[0]:
                for player in alive_players:
                    role = get_role(player, "role")
                    templates = get_role(player, "templates")
                    member = client.get_server(WEREWOLF_SERVER).get_member(player)
                    if "assassin" in templates and not [
                        x for x in session[1][player][4] if x.startswith("assassinate:")
                    ]:
                        possible_targets = [
                            x
                            for x in session[1]
                            if session[1][x][0]
                            and "luck_totem2" not in session[1][x][4]
                            and x != player
                            and not (
                                get_role(x, "role") == "succubus"
                                and "entranced" in session[1][player][4]
                            )
                        ]
                        if possible_targets:
                            target = random.choice(possible_targets)
                        else:
                            target = random.choice(
                                [
                                    x
                                    for x in session[1]
                                    if session[1][x][0]
                                    and x != player
                                    and not (
                                        get_role(x, "role") == "succubus"
                                        and "entranced" in session[1][player][4]
                                    )
                                ]
                            )
                        session[1][player][4].append("assassinate:{}".format(target))
                        log_msg.append(
                            "{0} ({1}) TARGET RANDOMLY {2} ({3})".format(
                                get_name(player), player, get_name(target), target
                            )
                        )
                        if member:
                            try:
                                await client.send_message(
                                    member,
                                    "Because you forgot to select a target at night, you are now targeting **{0}**.".format(
                                        get_name(target)
                                    ),
                                )
                            except discord.Forbidden:
                                pass
                    if (
                        "silence_totem2" in session[1][player][4]
                        and role != "matchmaker"
                    ):
                        continue
                    if (
                        role in ["shaman", "crazed shaman"]
                        and session[1][player][2] in totems
                    ) or (
                        role == "wolf shaman"
                        and [x for x in session[1][player][4] if x.startswith("totem:")]
                    ):
                        possible_targets = [
                            x
                            for x in session[1]
                            if session[1][x][0]
                            and "luck_totem2" not in session[1][x][4]
                            and x != player
                            and not (
                                get_role(x, "role") == "succubus"
                                and "entranced" in session[1][player][4]
                            )
                            and "lasttarget:{}".format(x) not in session[1][player][4]
                        ]
                        if possible_targets:
                            totem_target = random.choice(possible_targets)
                        else:
                            possible_targets = [
                                x
                                for x in session[1]
                                if session[1][x][0]
                                and x != player
                                and not (
                                    get_role(x, "role") == "succubus"
                                    and "entranced" in session[1][player][4]
                                )
                                and "lasttarget:{}".format(x)
                                not in session[1][player][4]
                            ]
                            if possible_targets:
                                totem_target = random.choice(possible_targets)
                            else:
                                totem_target = random.choice(
                                    [
                                        x
                                        for x in session[1]
                                        if session[1][x][0]
                                        and x != player
                                        and not (
                                            get_role(x, "role") == "succubus"
                                            and "entranced" in session[1][player][4]
                                        )
                                    ]
                                )
                        if role in ["shaman", "crazed shaman"]:
                            totem = session[1][player][2]
                        else:
                            totem = [
                                x
                                for x in session[1][player][4]
                                if x.startswith("totem:")
                            ][0].split(":")[1]
                        session[1][totem_target][4].append(totem)
                        if role in ["shaman", "crazed shaman"]:
                            session[1][player][2] = totem_target
                        session[1][player][4] = [
                            x
                            for x in session[1][player][4]
                            if not x.startswith("lasttarget")
                        ] + ["lasttarget:{}".format(totem_target)]
                        log_msg.append(
                            player + "'s " + totem + " given to " + totem_target
                        )
                        if member:
                            try:
                                random_given = (
                                    "wtf? this is a bug; pls report to admins"
                                )
                                if role in ["shaman", "wolf shaman"]:
                                    random_given = "Because you forgot to give your totem out at night, your **{0}** was randomly given to **{1}**.".format(
                                        totem.replace("_", " "), get_name(totem_target)
                                    )
                                elif role == "crazed shaman":
                                    random_given = "Because you forgot to give your totem out at night, your totem was randomly given to **{0}**.".format(
                                        get_name(totem_target)
                                    )
                                await client.send_message(member, random_given)
                            except discord.Forbidden:
                                pass
                    elif (
                        role == "matchmaker"
                        and "match" in session[1][player][4]
                        and str(session[4][1]) == "0:00:00"
                    ):
                        trycount = 0
                        alreadytried = []
                        while True:
                            player1 = random.choice(
                                [x for x in session[1] if session[1][x][0]]
                            )
                            player2 = random.choice(
                                [
                                    x
                                    for x in session[1]
                                    if session[1][x][0] and x != player1
                                ]
                            )
                            if not (
                                "lover:" + player2 in session[1][player1][4]
                                or "lover:" + player1 in session[1][player2][4]
                            ):
                                session[1][player][4].remove("match")
                                session[1][player1][4].append("lover:" + player2)
                                session[1][player2][4].append("lover:" + player1)
                                try:
                                    await client.send_message(
                                        client.get_server(WEREWOLF_SERVER).get_member(
                                            player1
                                        ),
                                        "You are in love with **{0}**. If that player dies for any reason, the pain will be too much for you to bear and you will commit suicide.".format(
                                            get_name(player2)
                                        ),
                                    )
                                except BaseException:
                                    pass
                                try:
                                    await client.send_message(
                                        client.get_server(WEREWOLF_SERVER).get_member(
                                            player2
                                        ),
                                        "You are in love with **{0}**. If that player dies for any reason, the pain will be too much for you to bear and you will commit suicide.".format(
                                            get_name(player1)
                                        ),
                                    )
                                except BaseException:
                                    pass
                                await log(
                                    1,
                                    "{0} ({1}) MATCH {2} ({3}) AND {4} ({5})".format(
                                        get_name(player),
                                        player,
                                        get_name(player1),
                                        player1,
                                        get_name(player2),
                                        player2,
                                    ),
                                )
                                break
                            elif [player1 + player2] not in alreadytried:
                                trycount += 1
                                alreadytried.append([player1 + player2])
                            if trycount >= (
                                len([x for x in session[1] if session[1][x][0]])
                                * (len([x for x in session[1] if session[1][x][0]]) - 1)
                            ):  # all possible lover sets are done
                                break
                        try:
                            await client.send_message(
                                client.get_server(WEREWOLF_SERVER).get_member(player),
                                "Because you forgot to choose lovers at night, two lovers have been selected for you.",
                            )
                        except BaseException:
                            pass
                    elif role == "piper" and "charm" in session[1][player][4]:
                        log_msg.append(
                            "{0} ({1}) PASS".format(get_name(player), player)
                        )
                        if member:
                            try:
                                await client.send_message(
                                    member,
                                    "You have chosen not to charm anyone tonight.",
                                )
                            except discord.Forbidden:
                                pass
                    elif role == "harlot" and session[1][player][2] == "":
                        session[1][player][2] = player
                        log_msg.append(
                            "{0} ({1}) STAY HOME".format(get_name(player), player)
                        )
                        if member:
                            try:
                                await client.send_message(
                                    member, "You will stay home tonight."
                                )
                            except discord.Forbidden:
                                pass
                    elif role == "succubus" and session[1][player][2] == "":
                        session[1][player][2] = player
                        log_msg.append(
                            "{0} ({1}) STAY HOME".format(get_name(player), player)
                        )
                        if member:
                            try:
                                await client.send_message(
                                    member,
                                    "You have chosen to not entrance anyone tonight.",
                                )
                            except discord.Forbidden:
                                pass
                    elif role == "hunter" and session[1][player][2] == "":
                        session[1][player][2] = player
                        log_msg.append(
                            "{0} ({1}) PASS".format(get_name(player), player)
                        )
                        if member:
                            try:
                                await client.send_message(
                                    member,
                                    "You have chosen to not kill anyone tonight.",
                                )
                            except discord.Forbidden:
                                pass
                    elif role == "serial killer" and session[1][player][2] == "":
                        session[1][player][2] = player
                        log_msg.append(
                            "{0} ({1}) PASS".format(get_name(player), player)
                        )
                        if member:
                            try:
                                await client.send_message(
                                    member,
                                    "You have chosen to not kill anyone tonight.",
                                )
                            except discord.Forbidden:
                                pass
                    elif role == "guardian angel" and session[1][player][2] in [
                        "pass",
                        "",
                    ]:
                        session[1][player][2] = ""
                        session[1][player][4][:] = [
                            x
                            for x in session[1][player][4]
                            if not x.startswith("lasttarget:")
                        ]
                        # clear previous target since no target selected
                        log_msg.append(
                            "{0} ({1}) NO GUARD".format(get_name(player), player)
                        )
                        if member and not session[1][player][2]:
                            try:
                                await client.send_message(
                                    member,
                                    "You have chosen to not guard anyone tonight.",
                                )
                            except discord.Forbidden:
                                pass
                    elif (
                        role == "vengeful ghost"
                        and session[1][player][2] == ""
                        and "consecrated" not in session[1][player][4]
                        and "driven" not in session[1][player][4]
                        and "notargets" not in session[1][player][4]
                    ):
                        against = "wolf"
                        if [
                            x
                            for x in session[1][player][4]
                            if x.startswith("vengeance:")
                        ]:
                            against = [
                                x.split(":")[1]
                                for x in session[1][player][4]
                                if x.startswith("vengeance:")
                            ].pop()
                        possible_targets = [
                            x
                            for x in session[1]
                            if session[1][x][0]
                            and "luck_totem2" not in session[1][x][4]
                            and get_role(x, "actualteam") == against
                        ]
                        if possible_targets:
                            target = random.choice(possible_targets)
                        else:
                            target = random.choice(
                                [
                                    x
                                    for x in session[1]
                                    if session[1][x][0]
                                    and get_role(x, "actualteam") == against
                                ]
                            )
                        session[1][player][2] = target
                        log_msg.append(
                            "{0} ({1}) VENGEFUL KILL {2} ({3})".format(
                                get_name(player), player, get_name(target), target
                            )
                        )
                    # randomly choose clone targets if unchosen
                    elif role == "clone" and "clone" in session[1][player][4]:
                        target = random.choice(
                            [x for x in session[1] if session[1][x][0] and x != player]
                        )
                        session[1][player][4].append("clone:{}".format(target))
                        if member:
                            try:
                                await client.send_message(
                                    member,
                                    "Because you did not choose someone to clone, you are cloning **{}**. If they die you will take their role.".format(
                                        get_name(target)
                                    ),
                                )
                            except discord.Forbidden:
                                pass
                        session[1][player][4].remove("clone")
                        await log(
                            1,
                            "{0} ({1}) CLONE TARGET {2} ({3})".format(
                                get_name(player), player, get_name(target), target
                            ),
                        )
                    # turncoat siding
                    elif role == "turncoat" and session[1][player][2]:
                        if session[1][player][2] == "wolves":
                            session[1][player][4].append("sided")
                            session[1][player][4].append("side:wolves")
                            if "side:villagers" in session[1][player][4]:
                                session[1][player][4].remove("side:villagers")
                        elif session[1][player][2] == "villagers":
                            session[1][player][4].append("sided")
                            session[1][player][4].append("side:villagers")
                            if "side:wolves" in session[1][player][4]:
                                session[1][player][4].remove("side:wolves")

            # BELUNGA
            for player in [x for x in session[1] if session[1][x][0]]:
                for i in range(session[1][player][4].count("belunga_totem")):
                    session[1][player][4].append(
                        random.choice(list(totems) + ["belunga_totem", "bullet"])
                    )
                    if (
                        random.random() < 0.1
                        and "gunner" not in get_role(player, "templates")
                        and "sharpshooter" not in get_role(player, "templates")
                    ):
                        session[1][player][3].append("gunner")
                        session[1][player][4].append("gunnotify")

            # Wolf kill
            wolf_votes = {}
            wolf_killed = []
            gunner_revenge = []
            wolf_deaths = []
            wolf_turn = []

            for player in alive_players:
                if (
                    roles[get_role(player, "role")][0] == "wolf"
                    and get_role(player, "role") in COMMANDS_FOR_ROLE["kill"]
                ):
                    for t in session[1][player][2].split(","):
                        if t in wolf_votes:
                            wolf_votes[t] += 1
                        elif t != "":
                            wolf_votes[t] = 1
            if wolf_votes != {}:
                sorted_votes = sorted(
                    wolf_votes, key=lambda x: wolf_votes[x], reverse=True
                )
                wolf_killed = sort_players(sorted_votes[:num_kills])
                log_msg.append(
                    "WOLFKILL: "
                    + ", ".join("{} ({})".format(get_name(x), x) for x in wolf_killed)
                )
                for k in wolf_killed:
                    if get_role(k, "role") == "harlot" and session[1][k][2] != k:
                        killed_msg += "The wolves' selected victim was not at home last night, and avoided the attack.\n"
                    elif get_role(k, "role") in ["monster", "serial killer"]:
                        pass
                    else:
                        killed_dict[k] += 1
                        wolf_deaths.append(k)

            # Guardian Angel stuff
            guarded = []
            guardeded = []  # like protect_totemed

            for angel in [
                x for x in alive_players if get_role(x, "role") == "guardian angel"
            ]:
                target = session[1][angel][2]
                if (
                    target
                ):  # GA makes more sense working on target even if they are harlot not at home
                    killed_dict[target] -= 50
                    guarded.append(target)

            # Harlot stuff
            for harlot in [x for x in alive_players if get_role(x, "role") == "harlot"]:
                visited = session[1][harlot][2]
                if visited != harlot:
                    # Depending on the mechanic that is wanted, ('blessed' in
                    # session[1][visited][4]) should either be changed to
                    # ('blessed' in session[1][visited][3]) or be removed
                    if visited in wolf_killed and not (
                        "protection_totem" in session[1][visited][4]
                        or "blessed" in session[1][visited][4]
                        or harlot in guarded
                    ):
                        killed_dict[harlot] += 1
                        killed_msg += "**{}**, a **harlot**, made the unfortunate mistake of visiting the victim's house last night and is now dead.\n".format(
                            get_name(harlot)
                        )
                        wolf_deaths.append(harlot)
                    elif (
                        get_role(visited, "role") in ACTUAL_WOLVES
                        and harlot not in guarded
                    ):
                        killed_dict[harlot] += 1
                        killed_msg += "**{}**, a **harlot**, made the unfortunate mistake of visiting a wolf's house last night and is now dead.\n".format(
                            get_name(harlot)
                        )
                        wolf_deaths.append(harlot)

            # Succubus stuff
            for succubus in [
                x for x in alive_players if get_role(x, "role") == "succubus"
            ]:
                visited = session[1][succubus][2]
                if visited != succubus:
                    # Depending on the mechanic that is wanted, ('blessed' in
                    # session[1][visited][4]) should either be changed to
                    # ('blessed' in session[1][visited][3]) or be removed
                    if visited in wolf_killed and not (
                        "protection_totem" in session[1][visited][4]
                        or "blessed" in session[1][visited][4]
                        or succubus in guarded
                    ):
                        killed_dict[succubus] += 1
                        killed_msg += "**{}**, a **succubus**, made the unfortunate mistake of visiting the victim's house last night and is now dead.\n".format(
                            get_name(succubus)
                        )
                        wolf_deaths.append(succubus)
            for disobeyer in [
                x for x in alive_players if "disobey" in session[1][x][4]
            ]:
                if random.random() < 0.5:
                    # this is what happens to bad bois
                    killed_dict[disobeyer] += 100

            # Hag stuff
            for hag in [x for x in alive_players if get_role(x, "role") == "hag"]:
                hexed = session[1][hag][2]
                if hexed:
                    session[1][hexed][4].append("hex")

            # Doomsayer stuff
            doom_deaths = []

            for doomsayer in [
                x
                for x in session[1]
                if get_role(x, "role") == "doomsayer"
                and [a for a in session[1][x][4] if a.startswith("doomdeath:")]
            ]:
                target = [
                    a.split(":")[1]
                    for a in session[1][doomsayer][4]
                    if a.startswith("doomdeath:")
                ].pop()
                killed_dict[target] += 1
                doom_deaths.append(target)
                session[1][doomsayer][4] = [
                    a
                    for a in session[1][doomsayer][4]
                    if not a.startswith("doomdeath:")
                ]

            # Hunter stuff
            for hunter in [x for x in session[1] if get_role(x, "role") == "hunter"]:
                target = session[1][hunter][2]
                if target not in [hunter, ""]:
                    if "hunterbullet" in session[1][hunter][4]:
                        session[1][hunter][4].remove("hunterbullet")
                        killed_dict[target] += 100

            # Serial killer stuff
            sk_deaths = []

            for sk in [x for x in session[1] if get_role(x, "role") == "serial killer"]:
                target = session[1][sk][2]
                if target not in [sk, ""]:
                    killed_dict[target] += 1
                    sk_deaths.append(target)

            # Vengeful ghost stuff
            for ghost in [
                x
                for x in session[1]
                if get_role(x, "role") == "vengeful ghost"
                and not session[1][x][0]
                and [a for a in session[1][x][4] if a.startswith("vengeance:")]
            ]:
                target = session[1][ghost][2]
                if target:
                    killed_dict[target] += 1
                    session[1][target][4].append("vg_target")
                    if "retribution_totem2" in session[1][target][4]:
                        session[1][ghost][4].append("driven")
                        killed_msg += "**{0}**'s totem emitted a brilliant flash of light last night. It appears that **{1}**'s spirit was driven away by the flash.\n".format(
                            get_name(target), get_name(ghost)
                        )

            # Bodyguard stuff
            for bodyguard in [
                x for x in alive_players if get_role(x, "role") == "bodyguard"
            ]:
                target = session[1][bodyguard][2]
                if (
                    target in session[1]
                    and (
                        target in wolf_deaths
                        or target in sk_deaths
                        or "vg_target" in session[1][target][4]
                    )
                    and not (
                        "protection_totem" in session[1][target][4]
                        or "blessed" in session[1][target][4]
                        or bodyguard in guarded
                    )
                ):
                    killed_dict[bodyguard] += 1
                    killed_dict[target] -= 1
                    if "protection_totem" not in session[1][bodyguard][4]:
                        killed_msg += "**{}** sacrificed their life to guard that of another.\n".format(
                            get_name(bodyguard)
                        )
                    if target in wolf_deaths:
                        wolf_deaths.append(bodyguard)
                        wolf_deaths.remove(target)
                    # elif get_role(target, 'role') in ACTUAL_WOLVES:
                    #    killed_dict[bodyguard] += 1
                    #    killed_msg += "**{}**, a **bodyguard**, made the unfortunate mistake of guarding a wolf last night and is now dead.\n".format(get_name(bodyguard))
                    #    wolf_deaths.append(bodyguard)
            for player in [x for x in session[1] if "vg_target" in session[1][x][4]]:
                session[1][player][4].remove("vg_target")

            # Totem stuff
            protect_totemed = []
            death_totemed = []
            ill_wolves = []
            revengekill = ""

            for player in sort_players(session[1]):
                prot_tots = 0
                death_tots = 0
                death_tots += session[1][player][4].count("death_totem")
                killed_dict[player] += death_tots
                if (
                    get_role(player, "role") != "harlot"
                    or session[1][player][2] == player
                ):
                    # fix for harlot with protect
                    prot_tots = session[1][player][4].count("protection_totem")
                    killed_dict[player] -= prot_tots
                if (
                    player in wolf_killed
                    and killed_dict[player] < 1
                    and not (
                        get_role(player, "role") == "harlot"
                        and session[1][player][2] != player
                    )
                ):
                    # if player was targeted by wolves but did not die and was
                    # not harlot avoiding attack
                    if player in guarded:
                        guardeded.append(player)
                    elif "protection_totem" in session[1][player][4]:
                        protect_totemed.append(player)
                if (
                    "death_totem" in session[1][player][4]
                    and killed_dict[player] > 0
                    and death_tots - prot_tots - guarded.count(player) > 0
                ):
                    death_totemed.append(player)

                if "cursed_totem" in session[1][player][4]:
                    if "cursed" not in get_role(player, "templates"):
                        session[1][player][3].append("cursed")

                if (
                    player in wolf_deaths
                    and killed_dict[player] > 0
                    and player not in death_totemed
                ):
                    # player was targeted and killed by wolves
                    if (
                        session[1][player][4].count("lycanthropy_totem2") > 0
                        or get_role(player, "role") == "lycan"
                        or "lycanthropy2" in session[1][player][4]
                    ):
                        killed_dict[player] -= 1
                        if killed_dict[player] == 0:
                            wolf_turn.append(player)
                            await wolfchat(
                                "{} is now a **wolf**!".format(get_name(player))
                            )
                            if get_role(player, "role") == "lycan":
                                lycan_message = (
                                    "HOOOOOOOOOWL. You have become... a wolf!"
                                )
                            elif "lycanthropy2" in session[1][player][4]:
                                lycan_message = "You awake to a sharp pain, and realize you are being attacked by a werewolf! You suddenly feel the weight of fate upon you, and find yourself turning into a werewolf!"
                            else:
                                lycan_message = "You awake to a sharp pain, and realize you are being attacked by a werewolf! Your totem emits a bright flash of light, and you find yourself turning into a werewolf!"
                            try:
                                member = client.get_server(WEREWOLF_SERVER).get_member(
                                    player
                                )
                                if member:
                                    await client.send_message(member, lycan_message)
                            except discord.Forbidden:
                                pass
                    elif "pestilence_totem2" in session[1][player][4]:
                        for p in session[1]:
                            if (
                                roles[get_role(p, "role")][0] == "wolf"
                                and get_role(p, "role") in COMMANDS_FOR_ROLE["kill"]
                            ):
                                ill_wolves.append(p)
                    if (
                        session[1][player][4].count("retribution_totem") > 0
                        and player not in wolf_turn
                    ):
                        revenge_targets = [
                            x
                            for x in session[1]
                            if session[1][x][0]
                            and get_role(x, "role")
                            in [
                                "wolf",
                                "doomsayer",
                                "werecrow",
                                "werekitten",
                                "wolf shaman",
                                "wolf mystic",
                            ]
                        ]
                        if get_role(player, "role") == "harlot" and get_role(
                            session[1][player][2], "role"
                        ) in [
                            "wolf",
                            "doomsayer",
                            "werecrow",
                            "wolf cub",
                            "werekitten",
                            "wolf shaman",
                            "wolf mystic",
                        ]:
                            revenge_targets[:] = [session[1][player][2]]
                        else:
                            revenge_targets[:] = [
                                x
                                for x in revenge_targets
                                if player in session[1][x][2].split(",")
                            ]
                        if revenge_targets:
                            revengekill = random.choice(revenge_targets)
                            killed_dict[revengekill] += 100
                            if killed_dict[revengekill] > 0:
                                killed_msg += "While being attacked last night, **{}**'s totem emitted a bright flash of light. The dead body of **{}**".format(
                                    get_name(player), get_name(revengekill)
                                )
                                killed_msg += (
                                    ", a **{}**, was found at the scene.\n".format(
                                        get_role(revengekill, "role")
                                    )
                                )

            for player in session[1]:
                session[1][player][4] = [
                    x for x in session[1][player][4] if x != "ill_wolf"
                ]
            for wolf in ill_wolves:
                session[1][wolf][4].append("ill_wolf")

            gun_rev = {}

            for player in sort_players(wolf_deaths):
                if (
                    (
                        "gunner" in get_role(player, "templates")
                        or "sharpshooter" in get_role(player, "templates")
                    )
                    and session[1][player][4].count("bullet") > 0
                    and killed_dict[player] > 0
                ):
                    target = ""
                    if random.random() < GUNNER_REVENGE_WOLF:
                        revenge_targets = [
                            x
                            for x in session[1]
                            if session[1][x][0]
                            and get_role(x, "role")
                            in [
                                "wolf",
                                "doomsayer",
                                "werecrow",
                                "werekitten",
                                "wolf shaman",
                                "wolf mystic",
                            ]
                        ]
                        if get_role(player, "role") == "harlot" and get_role(
                            session[1][player][2], "role"
                        ) in [
                            "wolf",
                            "doomsayer",
                            "werecrow",
                            "wolf cub",
                            "werekitten",
                            "wolf shaman",
                            "wolf mystic",
                        ]:
                            revenge_targets[:] = [session[1][player][2]]
                        else:
                            revenge_targets[:] = [
                                x
                                for x in revenge_targets
                                if session[1][x][2] in wolf_killed
                            ]
                        revenge_targets[:] = [
                            x for x in revenge_targets if x not in gunner_revenge
                        ]
                        if revenge_targets:
                            target = random.choice(revenge_targets)
                            gunner_revenge.append(target)
                            session[1][player][4].remove("bullet")
                            killed_dict[target] += 100
                            if killed_dict[target] > 0:
                                gun_rev[player] = target
                    if session[1][player][4].count("bullet") > 0:
                        give_gun_targets = [
                            x
                            for x in session[1]
                            if session[1][x][0]
                            and get_role(x, "role") in WOLFCHAT_ROLES
                            and x != target
                        ]
                        if len(give_gun_targets) > 0:
                            give_gun = random.choice(give_gun_targets)
                            if "gunner" not in get_role(give_gun, "templates"):
                                session[1][give_gun][3].append("gunner")
                            session[1][give_gun][4].append("bullet")
                            member = client.get_server(WEREWOLF_SERVER).get_member(
                                give_gun
                            )
                            if member:
                                try:
                                    await client.send_message(
                                        member,
                                        "While searching through **{}**'s belongings, you discover a gun loaded with 1 "
                                        "silver bullet! You may only use it during the day. If you shoot at a wolf, you will intentionally miss. If you "
                                        "shoot a villager, it is likely that they will be injured.".format(
                                            get_name(player)
                                        ),
                                    )
                                except discord.Forbidden:
                                    pass

            for player in killed_dict:
                if killed_dict[player] > 0:
                    killed_players.append(player)

            killed_players = sort_players(killed_players)

            killed_temp = killed_players[:]

            log_msg.append(
                "PROTECT_TOTEMED: "
                + ", ".join("{} ({})".format(get_name(x), x) for x in protect_totemed)
            )
            if guarded:
                log_msg.append(
                    "GUARDED: "
                    + ", ".join("{} ({})".format(get_name(x), x) for x in guarded)
                )
            if guardeded:
                log_msg.append(
                    "ACTUALLY GUARDED: "
                    + ", ".join("{} ({})".format(get_name(x), x) for x in guardeded)
                )
            log_msg.append(
                "DEATH_TOTEMED: "
                + ", ".join("{} ({})".format(get_name(x), x) for x in death_totemed)
            )
            log_msg.append(
                "PLAYERS TURNED WOLF: "
                + ", ".join("{} ({})".format(get_name(x), x) for x in wolf_turn)
            )
            if revengekill:
                log_msg.append(
                    "RETRIBUTED: "
                    + "{} ({})".format(get_name(revengekill), revengekill)
                )
            if gunner_revenge:
                log_msg.append(
                    "GUNNER_REVENGE: "
                    + ", ".join(
                        "{} ({})".format(get_name(x), x) for x in gunner_revenge
                    )
                )
            log_msg.append(
                "DEATHS FROM WOLF: "
                + ", ".join("{} ({})".format(get_name(x), x) for x in wolf_deaths)
            )
            log_msg.append(
                "DEATHS FROM SERIAL KILLERS: "
                + ", ".join("{} ({})".format(get_name(x), x) for x in sk_deaths)
            )
            log_msg.append(
                "KILLED PLAYERS: "
                + ", ".join("{} ({})".format(get_name(x), x) for x in killed_players)
            )

            await log(1, "\n".join(log_msg))

            if guardeded:
                for gded in sort_players(guardeded):
                    killed_msg += "**{0}** was attacked last night, but luckily the guardian angel was on duty.\n".format(
                        get_name(gded)
                    )

            if protect_totemed:
                for protected in sort_players(protect_totemed):
                    killed_msg += "**{0}** was attacked last night, but their totem emitted a brilliant flash of light, blinding their attacker and allowing them to escape.\n".format(
                        get_name(protected)
                    )

            if death_totemed:
                for ded in sort_players(death_totemed):
                    if session[6] == "noreveal":
                        killed_msg += "**{0}**'s totem emitted a brilliant flash of light last night. The dead body of **{0}** was found at the scene.\n".format(
                            get_name(ded)
                        )
                    else:
                        killed_msg += "**{0}**'s totem emitted a brilliant flash of light last night. The dead body of **{0}**, a **{1}** was found at the scene.\n".format(
                            get_name(ded), get_role(ded, "death")
                        )
                    killed_players.remove(ded)

            if revengekill and revengekill in killed_players:
                # retribution totem
                killed_players.remove(revengekill)

            for player in gunner_revenge:
                if player in killed_players:
                    killed_players.remove(player)

            if len(killed_players) == 0:
                if not (
                    guardeded
                    or protect_totemed
                    or death_totemed
                    or [x for x in wolf_killed if get_role(x, "role") == "harlot"]
                ):
                    killed_msg += random.choice(lang["nokills"]) + "\n"
            elif len(killed_players) == 1:
                if session[6] == "noreveal":
                    killed_msg += "The dead body of **{}** was found. Those remaining mourn the tragedy.\n".format(
                        get_name(killed_players[0])
                    )
                else:
                    killed_msg += "The dead body of **{}**, a **{}**, was found. Those remaining mourn the tragedy.\n".format(
                        get_name(killed_players[0]),
                        get_role(killed_players[0], "death"),
                    )
            else:
                if session[6] == "noreveal":
                    if len(killed_players) == 2:
                        killed_msg += "The dead bodies of **{0}** and **{1}** were found. Those remaining mourn the tragedy.\n".format(
                            get_name(killed_players[0]), get_name(killed_players[1])
                        )
                    else:
                        killed_msg += "The dead bodies of **{0}**, and **{1}** were found. Those remaining mourn the tragedy.\n".format(
                            "**, **".join(map(get_name, killed_players[:-1])),
                            get_name(killed_players[-1]),
                        )
                else:
                    killed_msg += "The dead bodies of **{}**, and **{}**, a **{}**, were found. Those remaining mourn the tragedy.\n".format(
                        "**, **".join(
                            get_name(x) + "**, a **" + get_role(x, "death")
                            for x in killed_players[:-1]
                        ),
                        get_name(killed_players[-1]),
                        get_role(killed_players[-1], "death"),
                    )

            if gun_rev:
                if session[6] == "noreveal":
                    for player in gun_rev:
                        killed_msg += "Fortunately **{}** had bullets and **{}** was shot dead.\n".format(
                            get_name(player), get_name(gun_rev[player])
                        )
                else:
                    for player in gun_rev:
                        killed_msg += "Fortunately **{}** had bullets and **{}**, a **{}**, was shot dead.\n".format(
                            get_name(player),
                            get_name(gun_rev[player]),
                            get_role(gun_rev[player], "death"),
                        )

            if session[0] and win_condition() is None:
                await send_lobby(
                    "Night lasted **{0:02d}:{1:02d}**. The villagers wake up and search the village.\n\n{2}".format(
                        night_elapsed.seconds // 60,
                        night_elapsed.seconds % 60,
                        killed_msg,
                    )
                )
                for player in session[1]:
                    session[1][player][4] = [
                        o for o in session[1][player][4] if o != "angry"
                    ]

            killed_dict = {}
            for player in killed_temp:
                kill_team = (
                    "wolf"
                    if player not in gunner_revenge + list(revengekill) + death_totemed
                    and (player in wolf_deaths or player in doom_deaths)
                    else "village"
                )
                killed_dict[player] = ("night kill", kill_team)
            if killed_dict:
                await player_deaths(killed_dict)

            for player in wolf_turn:
                session[1][player][4].append(
                    "turned:{}".format(get_role(player, "role"))
                )
                session[1][player][1] = "wolf"

            # Hot potato stuff
            for potato in [
                x
                for x in session[1]
                if session[1][x][0] and get_role(x, "role") == "hot potato"
            ]:
                target = session[1][potato][2]
                if target:
                    if target in [x for x in session[1] if session[1][x][0]]:
                        role = get_role(target, "role")
                        templates = [x for x in session[1][target][3]]
                        other = [x for x in session[1][target][4]]
                        session[1][target][1] = "hot potato"
                        session[1][target][3] = [x for x in session[1][potato][3]]
                        session[1][target][4] = [x for x in session[1][potato][4]]
                        session[1][potato][1] = role
                        session[1][potato][3] = templates
                        session[1][potato][4] = other
                        try:
                            target_member = client.get_server(
                                WEREWOLF_SERVER
                            ).get_member(target)
                            if target_member:
                                await client.send_message(
                                    target_member,
                                    "You are now a **hot potato**!\nYour role is **hot potato**. {}\n".format(
                                        roles["hot potato"][2]
                                    ),
                                )
                            potato_member = client.get_server(
                                WEREWOLF_SERVER
                            ).get_member(potato)
                            if potato_member:
                                await client.send_message(
                                    potato_member,
                                    "You are now a **{0}**!\nYour role is **{0}**. {1}\n".format(
                                        role, roles[role][2]
                                    ),
                                )
                        except discord.Forbidden:
                            pass
                        for player in [
                            x
                            for x in session[1]
                            if session[1][x][0] and session[1][x][4]
                        ]:
                            new_other = []
                            member = client.get_server(WEREWOLF_SERVER).get_member(
                                player
                            )
                            for element in session[1][player][4]:
                                if element == "lover:{}".format(target):
                                    new_other.append("lover:{}".format(potato))
                                    try:
                                        if member:
                                            await client.send_message(
                                                member,
                                                "Your lover had their identity swapped, so you are now in love with **{}**!".format(
                                                    get_name(potato)
                                                ),
                                            )
                                    except discord.Forbidden:
                                        pass
                                elif element == "lover:{}".format(potato):
                                    new_other.append("lover:{}".format(target))
                                    try:
                                        if member:
                                            await client.send_message(
                                                member,
                                                "Your lover had their identity swapped, so you are now in love with **{}**!".format(
                                                    get_name(target)
                                                ),
                                            )
                                    except discord.Forbidden:
                                        pass
                                else:
                                    new_other.append(element)
                            session[1][player][4] = new_other
                        member = client.get_server(WEREWOLF_SERVER).get_member(potato)
                        if member:
                            try:
                                if role == "hunter":
                                    if "hunterbullet" in session[1][potato][4]:
                                        await client.send_message(
                                            member, "You have **not** shot anyone yet."
                                        )
                                    else:
                                        await client.send_message(
                                            member,
                                            "You have **already** shot someone this game.",
                                        )
                                elif role == "priest":
                                    if "bless" in session[1][potato][4]:
                                        await client.send_message(
                                            member,
                                            "You have **not** blessed anyone yet.",
                                        )
                                    else:
                                        await client.send_message(
                                            member,
                                            "You have **already** blessed someone this game.",
                                        )
                                elif role == "clone" and session[1][potato][4]:
                                    if [
                                        x
                                        for x in session[1][potato][4]
                                        if x.startswith("clone:")
                                    ]:
                                        await client.send_message(
                                            member,
                                            "You are cloning **{}**. If they die you will take their role.".format(
                                                get_name(
                                                    [
                                                        x
                                                        for x in session[1][potato][4]
                                                        if x.startswith("clone:")
                                                    ][0].strip("clone:")
                                                )
                                            ),
                                        )
                                elif role == "turncoat":
                                    if "side:villagers" in session[1][potato][4]:
                                        await client.send_message(
                                            member,
                                            "You are currently siding with the village.",
                                        )
                                    elif "side:wolves" in session[1][potato][4]:
                                        await client.send_message(
                                            member,
                                            "You are currently siding with the wolves.",
                                        )
                                    if "sided2" in session[1][potato][4]:
                                        await client.send_message(
                                            member,
                                            "You will be able to switch sides in two nights.",
                                        )
                                    else:
                                        await client.send_message(
                                            member,
                                            "You will be able to switch sides during the upcoming night.",
                                        )
                                elif role == "executioner":
                                    if [
                                        x
                                        for x in session[1][potato][4]
                                        if x.startswith("execute:")
                                    ]:
                                        exe_target = [
                                            x
                                            for x in session[1][potato][4]
                                            if x.startswith("execute:")
                                        ][0].strip("execute:")
                                        if "win" in session[1][potato][4]:
                                            await client.send_message(
                                                member,
                                                "Your target was **{}**. This player was lynched, so you won.".format(
                                                    get_name(exe_target)
                                                ),
                                            )
                                        else:
                                            await client.send_message(
                                                member,
                                                "Your target for lynch is **{}**.".format(
                                                    get_name(exe_target)
                                                ),
                                            )
                                    else:
                                        if [
                                            x
                                            for x in [
                                                y
                                                for y in session[1]
                                                if session[1][y][0]
                                            ]
                                            if get_role(x, "actualteam") == "village"
                                        ]:
                                            exe_target = random.choice(
                                                [
                                                    x
                                                    for x in [
                                                        y
                                                        for y in session[1]
                                                        if session[1][y][0]
                                                    ]
                                                    if get_role(x, "actualteam")
                                                    == "village"
                                                ]
                                            )
                                            session[1][potato][4].append(
                                                "execute:{}".format(exe_target)
                                            )
                                            await client.send_message(
                                                member,
                                                "Your target for lynch is **{}**.".format(
                                                    get_name(exe_target)
                                                ),
                                            )
                                        else:
                                            session[1][potato][1] = "jester"
                                            session[1][potato][4].append("executioner")
                                            await client.send_message(
                                                member,
                                                "There are no available targets. You have now become a **jester**.\nYour role is **jester**. {}\n".format(
                                                    roles["jester"][2]
                                                ),
                                            )
                                elif role == "minion":
                                    living_players_string = []
                                    for plr in [
                                        x for x in session[1] if session[1][x][0]
                                    ]:
                                        temprole = get_role(plr, "role")
                                        role_string = []
                                        if roles[temprole][
                                            0
                                        ] == "wolf" and temprole not in [
                                            "minion",
                                            "cultist",
                                        ]:
                                            role_string.append(temprole)
                                        living_players_string.append(
                                            "{} ({}){}".format(
                                                get_name(plr),
                                                plr,
                                                (
                                                    " ({})".format(
                                                        " ".join(role_string)
                                                    )
                                                    if role_string
                                                    else ""
                                                ),
                                            )
                                        )
                                    await client.send_message(
                                        member,
                                        "Living players: ```basic\n"
                                        + "\n".join(living_players_string)
                                        + "\n```",
                                    )
                            except discord.Forbidden:
                                pass
                        for player in [potato, target]:
                            member = client.get_server(WEREWOLF_SERVER).get_member(
                                player
                            )
                            if member:
                                try:
                                    if "gunner" in session[1][player][3]:
                                        await client.send_message(
                                            member,
                                            "You have a gun and **{}** bullet{}. Use the command `{}role gunner` for more information.".format(
                                                session[1][player][4].count("bullet"),
                                                (
                                                    ""
                                                    if session[1][player][4].count(
                                                        "bullet"
                                                    )
                                                    == 1
                                                    else "s"
                                                ),
                                                BOT_PREFIX,
                                            ),
                                        )
                                    if "sharpshooter" in session[1][player][3]:
                                        await client.send_message(
                                            member,
                                            "You have a gun and **{}** bullet{}. Use the command `{}role sharpshooter` for more information.".format(
                                                session[1][player][4].count("bullet"),
                                                (
                                                    ""
                                                    if session[1][player][4].count(
                                                        "bullet"
                                                    )
                                                    == 1
                                                    else "s"
                                                ),
                                                BOT_PREFIX,
                                            ),
                                        )
                                    if session[1][player][4]:
                                        if "assassin" in session[1][player][3] and [
                                            x
                                            for x in session[1][player][4]
                                            if x.startswith("assassinate:")
                                        ]:
                                            await client.send_message(
                                                member,
                                                "Your target is **{0}**. Use the command `{1}role assassin` for more information.".format(
                                                    get_name(
                                                        [
                                                            x
                                                            for x in session[1][player][
                                                                4
                                                            ]
                                                            if x.startswith(
                                                                "assassinate:"
                                                            )
                                                        ][0].strip("assassinate:")
                                                    ),
                                                    BOT_PREFIX,
                                                ),
                                            )
                                        for element in session[1][player][4]:
                                            if element == "entranced" and [
                                                x
                                                for x in session[1]
                                                if session[1][x][0]
                                                and get_role(x, "role") == "succubus"
                                            ]:
                                                await client.send_message(
                                                    member,
                                                    "You have become entranced, and are now on **{}**'s team. From this point on, you must vote along with them or risk dying. You **cannot win with your own team**, but you will win should all alive players become entranced.".format(
                                                        get_name(
                                                            random.choice(
                                                                [
                                                                    x
                                                                    for x in session[1]
                                                                    if session[1][x][0]
                                                                    and get_role(
                                                                        x, "role"
                                                                    )
                                                                    == "succubus"
                                                                ]
                                                            )
                                                        )
                                                    ),
                                                )
                                            elif element.startswith("lover:"):
                                                await client.send_message(
                                                    member,
                                                    "You are in love with **{}**. If that player dies for any reason, the pain will be too much for you to bear and you will commit suicide.".format(
                                                        get_name(
                                                            element.strip("lover:")
                                                        )
                                                    ),
                                                )
                                except discord.Forbidden:
                                    pass
                        if role in WOLFCHAT_ROLES:
                            try:
                                await wolfchat(
                                    "**{0}** has replaced **{1}** as a **{2}**!".format(
                                        get_name(potato), get_name(target), role
                                    )
                                )
                            except discord.Forbidden:
                                pass
                    else:
                        try:
                            member = client.get_server(WEREWOLF_SERVER).get_member(
                                potato
                            )
                            if member:
                                await client.send_message(
                                    member,
                                    "**{}** died this night, so you are still a **hot potato**.".format(
                                        get_name(target)
                                    ),
                                )
                        except discord.Forbidden:
                            pass

            for player in session[1]:
                session[1][player][2] = ""

            if session[0]:
                # Piper stuff
                charmed = sort_players(
                    [x for x in alive_players if "charmed" in session[1][x][4]]
                )
                tocharm = sort_players(
                    [x for x in alive_players if "tocharm" in session[1][x][4]]
                )
                for player in tocharm:
                    charmed_total = [x for x in charmed + tocharm if x != player]
                    session[1][player][4].remove("tocharm")
                    session[1][player][4].append("charmed")
                    piper_message = "You hear the sweet tones of a flute coming from outside your window... You inexorably walk outside and find yourself in the village square. "
                    if len(charmed_total) > 2:
                        piper_message += "You find out that **{0}**, and **{1}** are also charmed!".format(
                            "**, **".join(map(get_name, charmed_total[:-1])),
                            get_name(charmed_total[-1]),
                        )
                    elif len(charmed_total) == 2:
                        piper_message += "You find out that **{0}** and **{1}** are also charmed!".format(
                            get_name(charmed_total[0]), get_name(charmed_total[1])
                        )
                    elif len(charmed_total) == 1:
                        piper_message += (
                            "You find out that **{}** is also charmed!".format(
                                get_name(charmed_total[0])
                            )
                        )
                    try:
                        member = client.get_server(WEREWOLF_SERVER).get_member(player)
                        if member and piper_message:
                            await client.send_message(member, piper_message)
                    except discord.Forbidden:
                        pass
                fullcharmed = charmed + tocharm
                for player in charmed:
                    piper_message = ""
                    fullcharmed.remove(player)
                    if len(fullcharmed) > 1:
                        piper_message = (
                            "You, **{0}**, and **{1}** are all charmed!".format(
                                "**, **".join(map(get_name, fullcharmed[:-1])),
                                get_name(fullcharmed[-1]),
                            )
                        )
                    elif len(fullcharmed) == 1:
                        piper_message = "You and **{0}** are now charmed!".format(
                            get_name(fullcharmed[0])
                        )
                    elif len(fullcharmed) == 0:
                        piper_message = "You are the only charmed villager."
                    try:
                        member = client.get_server(WEREWOLF_SERVER).get_member(player)
                        if member and piper_message:
                            await client.send_message(member, piper_message)
                    except discord.Forbidden:
                        pass
                    fullcharmed.append(player)

                if win_condition() is None:
                    # More totem stuff
                    totem_holders = []
                    for player in sort_players(session[1]):
                        if [x for x in session[1][player][4] if x in totems]:
                            totem_holders.append(player)
                        other = session[1][player][4][:]
                        for o in other[:]:
                            # Hacky way to get specific mechanisms to last 2
                            # nights
                            group_remove = [
                                "death_totem",
                                "cursed_totem",
                                "retribution_totem",
                                "lycanthropy_totem2",
                                "deceit_totem2",
                                "misdirection_totem2",
                                "luck_totem2",
                                "silence_totem2",
                                "pestilence_totem2",
                                "charm",
                                "consecrated",
                                "disobey",
                                "illness",
                                "lycanthropy2",
                                "notargets",
                                "sided2",
                            ]
                            group_remove_append_two = [
                                "protection_totem",
                                "lycanthropy_totem",
                                "deceit_totem",
                                "misdirection_totem",
                                "luck_totem",
                                "silence_totem",
                                "pestilence_totem",
                                "lycanthropy",
                                "sided",
                            ]
                            group_remove_append_silence = ["hex", "sick"]
                            if (
                                o.startswith("given:")
                                or o.startswith("totem:")
                                or o.startswith("doom:")
                                or o
                                in group_remove
                                + group_remove_append_two
                                + group_remove_append_silence
                            ):
                                other.remove(o)
                                if o in group_remove_append_two:
                                    # protection_totem2 only protects from
                                    # assassin and mad scientist
                                    other.append("{}2".format(o))
                                elif o in group_remove_append_silence:
                                    other.append("silence_totem2")
                                    if o == "sick":
                                        other.append("illness")
                        session[1][player][4] = other
                    totem_holders = sort_players(totem_holders)
                    if len(totem_holders) == 0:
                        pass
                    elif len(totem_holders) == 1:
                        await send_lobby(
                            random.choice(lang["hastotem"]).format(
                                get_name(totem_holders[0])
                            )
                        )
                    elif len(totem_holders) == 2:
                        await send_lobby(
                            random.choice(lang["hastotem2"]).format(
                                get_name(totem_holders[0]), get_name(totem_holders[1])
                            )
                        )
                    else:
                        await send_lobby(
                            random.choice(lang["hastotems"]).format(
                                "**, **".join(
                                    [get_name(x) for x in totem_holders[:-1]]
                                ),
                                get_name(totem_holders[-1]),
                            )
                        )

                    await check_traitor()

        else:  # DAY
            session[3][1] = datetime.now()
            if session[0] and win_condition() is None:
                for player in session[1]:
                    session[1][player][4] = [
                        x
                        for x in session[1][player][4]
                        if x not in ["guarded", "protection_totem2"]
                        and not x.startswith("bodyguard:")
                    ]
                await send_lobby(
                    "It is now **daytime**. Use `{}lynch <player>` to vote to lynch <player>.".format(
                        BOT_PREFIX
                    )
                )

            for player in session[1]:
                if session[1][player][0] and "blinding_totem" in session[1][player][4]:
                    if "injured" not in session[1][player][4]:
                        session[1][player][4].append("injured")
                        for i in range(session[1][player][4].count("blinding_totem")):
                            session[1][player][4].remove("blinding_totem")
                        try:
                            member = client.get_server(WEREWOLF_SERVER).get_member(
                                player
                            )
                            if member:
                                await client.send_message(
                                    member,
                                    "Your totem emits a brilliant flash of light. "
                                    "It seems like you cannot see anything! Perhaps "
                                    "you should just rest during the day...",
                                )
                        except discord.Forbidden:
                            pass
                if "illness" in session[1][player][4]:
                    session[1][player][4].append("injured")
                if get_role(player, "role") == "doomsayer":
                    session[1][player][4] = [
                        x for x in session[1][player][4] if not x.startswith("doom:")
                    ]
            if session[6] != "mudkip":
                lynched_player = None
                warn = False
                totem_dict = {}  # For impatience and pacifism
                # DAY LOOP
                while (
                    win_condition() is None
                    and session[2]
                    and lynched_player is None
                    and session[0]
                ):
                    for player in [x for x in session[1]]:
                        totem_dict[player] = session[1][player][4].count(
                            "impatience_totem"
                        ) - session[1][player][4].count("pacifism_totem")
                    vote_dict = get_votes(totem_dict)
                    if (
                        vote_dict["abstain"]
                        >= len(
                            [
                                x
                                for x in session[1]
                                if session[1][x][0]
                                and "injured" not in session[1][x][4]
                            ]
                        )
                        / 2
                    ):
                        lynched_player = "abstain"
                    max_votes = max([vote_dict[x] for x in vote_dict])
                    max_voted = []
                    if (
                        max_votes
                        >= len(
                            [
                                x
                                for x in session[1]
                                if session[1][x][0]
                                and "injured" not in session[1][x][4]
                            ]
                        )
                        // 2
                        + 1
                    ):
                        for voted in vote_dict:
                            if vote_dict[voted] == max_votes:
                                max_voted.append(voted)
                        lynched_player = random.choice(max_voted)
                    if (datetime.now() - session[3][1]).total_seconds() > day_timeout:
                        # hopefully a fix for time being weird
                        session[3][0] = datetime.now()
                        session[2] = False
                    if (
                        datetime.now() - session[3][1]
                    ).total_seconds() > day_warning and not warn:
                        warn = True
                        await send_lobby(
                            "**As the sun sinks inexorably toward the horizon, turning the lanky pine "
                            "trees into fire-edged silhouettes, the villagers are reminded that very little time remains for them to reach a "
                            "decision; if darkness falls before they have done so, the majority will win the vote. No one will be lynched if "
                            "there are no votes or an even split.**"
                        )
                    await asyncio.sleep(0.1)
                if not lynched_player and win_condition() is None and session[0]:
                    vote_dict = get_votes(totem_dict)
                    max_votes = max([vote_dict[x] for x in vote_dict])
                    max_voted = []
                    for voted in vote_dict:
                        if vote_dict[voted] == max_votes and voted != "abstain":
                            max_voted.append(voted)
                    if len(max_voted) == 1:
                        lynched_player = max_voted[0]
                if session[0]:
                    # hopefully a fix for time being weird
                    session[3][0] = datetime.now()
                    day_elapsed = datetime.now() - session[3][1]
                    session[4][1] += day_elapsed
                lynched_msg = ""
                if lynched_player and win_condition() is None and session[0]:
                    if lynched_player == "abstain":
                        for player in [
                            x
                            for x in totem_dict
                            if session[1][x][0] and totem_dict[x] < 0
                        ]:
                            lynched_msg += "**{}** meekly votes to not lynch anyone today.\n".format(
                                get_name(player)
                            )
                        lynched_msg += (
                            "The village has agreed to not lynch anyone today."
                        )
                        await send_lobby(lynched_msg)
                    else:
                        for player in [
                            x
                            for x in totem_dict
                            if session[1][x][0]
                            and totem_dict[x] > 0
                            and x != lynched_player
                        ]:
                            lynched_msg += (
                                "**{}** impatiently votes to lynch **{}**.\n".format(
                                    get_name(player), get_name(lynched_player)
                                )
                            )
                        lynched_msg += "\n"
                        if lynched_player in session[1].keys():
                            if "revealing_totem" in session[1][lynched_player][4]:
                                lynched_msg += "As the villagers prepare to lynch **{0}**, their totem emits a brilliant flash of light! When the villagers are able to see again, "
                                lynched_msg += "they discover that {0} has escaped! The left-behind totem seems to have taken on the shape of a **{1}**."
                                if get_role(lynched_player, "role") == "amnesiac":
                                    role = [
                                        x.split(":")[1].replace("_", " ")
                                        for x in session[1][lynched_player][4]
                                        if x.startswith("role:")
                                    ].pop()
                                    session[1][lynched_player][1] = role
                                    session[1][lynched_player][4] = [
                                        x
                                        for x in session[1][lynched_player][4]
                                        if not x.startswith("role:")
                                    ]
                                    try:
                                        await client.send_message(
                                            client.get_server(
                                                WEREWOLF_SERVER
                                            ).get_member(lynched_player),
                                            "Your totem clears your amnesia and you now fully remember who you are!",
                                        )
                                        await _send_role_info(lynched_player)
                                        if role in WOLFCHAT_ROLES:
                                            await wolfchat(
                                                "{0} is now a **{1}**!".format(
                                                    get_name(lynched_player), role
                                                )
                                            )
                                    except discord.Forbidden:
                                        pass
                                lynched_msg = lynched_msg.format(
                                    get_name(lynched_player),
                                    get_role(lynched_player, "role"),
                                )
                                await send_lobby(lynched_msg)
                            elif (
                                "mayor" in get_role(lynched_player, "templates")
                                and "unrevealed" in session[1][lynched_player][4]
                            ):
                                lynched_msg += "While being dragged to the gallows, **{}** reveals that they are the **mayor**. The village agrees to let them live for now.".format(
                                    get_name(lynched_player)
                                )
                                session[1][lynched_player][4].remove("unrevealed")
                                await send_lobby(lynched_msg)
                            else:
                                if "luck_totem2" in session[1][lynched_player][4]:
                                    lynched_player = misdirect(lynched_player)
                                if session[6] == "noreveal":
                                    lynched_msg += random.choice(
                                        lang["lynchednoreveal"]
                                    ).format(get_name(lynched_player))
                                else:
                                    lynched_msg += random.choice(
                                        lang["lynched"]
                                    ).format(
                                        get_name(lynched_player),
                                        get_role(lynched_player, "death"),
                                    )
                                await send_lobby(lynched_msg)
                                if get_role(lynched_player, "role") == "jester":
                                    session[1][lynched_player][4].append("lynched")
                                for player in [
                                    x for x in session[1] if session[1][x][0]
                                ]:
                                    if (
                                        get_role(player, "role") == "executioner"
                                        and "win" not in session[1][player][4]
                                        and [
                                            x
                                            for x in session[1][player][4]
                                            if x.startswith("execute:")
                                        ]
                                    ):
                                        if [
                                            x
                                            for x in session[1][player][4]
                                            if x.startswith("execute:")
                                        ][0].strip("execute:") == lynched_player:
                                            session[1][player][4].append("win")
                                            member = client.get_server(
                                                WEREWOLF_SERVER
                                            ).get_member(player)
                                            if member:
                                                try:
                                                    await client.send_message(
                                                        member,
                                                        "Your target was **{}**. This player was lynched, so you won.".format(
                                                            get_name(lynched_player)
                                                        ),
                                                    )
                                                except discord.Forbidden:
                                                    pass
                                lynchers_team = [
                                    get_role(x, "actualteam")
                                    for x in session[1]
                                    if session[1][x][0]
                                    and session[1][x][2] == lynched_player
                                ]
                                await player_deaths(
                                    {
                                        lynched_player: (
                                            "lynch",
                                            (
                                                "wolf"
                                                if lynchers_team.count("wolf")
                                                > lynchers_team.count("village")
                                                else "village"
                                            ),
                                        )
                                    }
                                )

                            if (
                                get_role(lynched_player, "role") == "fool"
                                and "revealing_totem"
                                not in session[1][lynched_player][4]
                            ):
                                win_msg = (
                                    "The fool has been lynched, causing them to win!\n\n"
                                    + end_game_stats()
                                )
                                lovers = []
                                for n in session[1][lynched_player][4]:
                                    if n.startswith("lover:"):
                                        lover = n.split(":")[1]
                                        if session[1][lover][0]:
                                            lovers.append(lover)

                                await end_game(
                                    win_msg,
                                    [lynched_player]
                                    + (lovers if session[6] == "random" else [])
                                    + [
                                        x
                                        for x in session[1]
                                        if get_role(x, "role") == "jester"
                                        and "lynched" in session[1][x][4]
                                    ],
                                )
                                return
                elif lynched_player is None and win_condition() is None and session[0]:
                    await send_lobby("Not enough votes were cast to lynch a player.")
            else:
                lynched_players = []
                warn = False
                totem_dict = (
                    {}
                )  # For impatience and pacifism, which are not found in mudkip
                # DAY LOOP
                while (
                    win_condition() is None
                    and session[2]
                    and not lynched_players
                    and session[0]
                ):
                    for player in [x for x in session[1]]:
                        totem_dict[player] = 0
                    vote_dict = get_votes(totem_dict)
                    max_votes = max([vote_dict[x] for x in vote_dict])
                    if (
                        vote_dict["abstain"]
                        >= len(
                            [
                                x
                                for x in session[1]
                                if session[1][x][0]
                                and "injured" not in session[1][x][4]
                            ]
                        )
                        / 2
                    ):
                        lynched_players = "abstain"
                    elif max_votes >= len(
                        [
                            x
                            for x in session[1]
                            if session[1][x][0] and "injured" not in session[1][x][4]
                        ]
                    ) // 2 + 1 or not [
                        x
                        for x in session[1]
                        if not session[1][x][2] and session[1][x][0]
                    ]:
                        for voted in vote_dict:
                            if vote_dict[voted] == max_votes:
                                lynched_players.append(voted)
                    if (datetime.now() - session[3][1]).total_seconds() > day_timeout:
                        # hopefully a fix for time being weird
                        session[3][0] = datetime.now()
                        session[2] = False
                    if (
                        datetime.now() - session[3][1]
                    ).total_seconds() > day_warning and not warn:
                        warn = True
                        await send_lobby(
                            "**As the sun sinks inexorably toward the horizon, turning the lanky pine "
                            "trees into fire-edged silhouettes, the villagers are reminded that very little time remains for them to reach a "
                            "decision; if darkness falls before they have done so, the majority will win the vote. No one will be lynched if "
                            "there are no votes or an even split.**"
                        )
                    await asyncio.sleep(0.1)
                if not lynched_players and win_condition() is None and session[0]:
                    vote_dict = get_votes(totem_dict)
                    max_votes = max([vote_dict[x] for x in vote_dict])
                    max_voted = []
                    for voted in vote_dict:
                        if vote_dict[voted] == max_votes and voted != "abstain":
                            max_voted.append(voted)
                    if max_voted:
                        lynched_players = max_voted
                if session[0]:
                    # hopefully a fix for time being weird
                    session[3][0] = datetime.now()
                    day_elapsed = datetime.now() - session[3][1]
                    session[4][1] += day_elapsed
                lynched_msg = ""
                lynch_deaths = {}
                if lynched_players and win_condition() is None and session[0]:
                    if lynched_players == "abstain":
                        lynched_msg += (
                            "The village has agreed to not lynch anyone today."
                        )
                    else:
                        for lynched_player in lynched_players:
                            if lynched_player in session[1].keys():
                                lynched_msg += "\n"
                                lynched_msg += random.choice(lang["lynched"]).format(
                                    get_name(lynched_player),
                                    get_role(lynched_player, "death"),
                                )
                                if get_role(lynched_player, "role") == "jester":
                                    session[1][lynched_player][4].append("lynched")
                                lynchers_team = [
                                    get_role(x, "actualteam")
                                    for x in session[1]
                                    if session[1][x][0]
                                    and session[1][x][2] == lynched_player
                                ]
                                lynch_deaths.update(
                                    {
                                        lynched_player: (
                                            "lynch",
                                            (
                                                "wolf"
                                                if lynchers_team.count("wolf")
                                                > lynchers_team.count("village")
                                                else "village"
                                            ),
                                        )
                                    }
                                )
                    await send_lobby(lynched_msg)
                    await player_deaths(lynch_deaths)
            # BETWEEN DAY AND NIGHT
            session[2] = False
            night += 1
            if session[0] and win_condition() is None:
                await send_lobby(
                    "Day lasted **{0:02d}:{1:02d}**. The villagers, exhausted from the day's events, go to bed.".format(
                        day_elapsed.seconds // 60, day_elapsed.seconds % 60
                    )
                )
                for player in [
                    x
                    for x in session[1]
                    if session[1][x][0] and "entranced" in session[1][x][4]
                ]:
                    if session[1][player][2] not in [
                        session[1][x][2]
                        for x in session[1]
                        if session[1][x][0] and get_role(x, "role") == "succubus"
                    ]:
                        session[1][player][4].append("disobey")
                for player in session[1]:
                    session[1][player][4][:] = [
                        x
                        for x in session[1][player][4]
                        if x
                        not in [
                            "revealing_totem",
                            "influence_totem",
                            "impatience_totem",
                            "pacifism_totem",
                            "injured",
                            "desperation_totem",
                        ]
                    ]
                    session[1][player][2] = ""
                    session[1][player][4] = [
                        x for x in session[1][player][4] if not x.startswith("vote:")
                    ]
                    if (
                        get_role(player, "role") == "amnesiac"
                        and night == 3
                        and session[1][player][0]
                    ):
                        role = [
                            x.split(":")[1].replace("_", " ")
                            for x in session[1][player][4]
                            if x.startswith("role:")
                        ].pop()
                        session[1][player][1] = role
                        session[1][player][4] = [
                            x
                            for x in session[1][player][4]
                            if not x.startswith("role:")
                        ]
                        session[1][player][4].append("amnesiac")
                        try:
                            await client.send_message(
                                client.get_server(WEREWOLF_SERVER).get_member(player),
                                "Your amnesia clears and you now remember that you are a{0} **{1}**!".format(
                                    (
                                        "n"
                                        if role.lower()[0] in ["a", "e", "i", "o", "u"]
                                        else ""
                                    ),
                                    role,
                                ),
                            )
                            if role in WOLFCHAT_ROLES:
                                await wolfchat(
                                    "{0} is now a **{1}**!".format(
                                        get_name(player), role
                                    )
                                )
                        except BaseException:
                            pass
                await check_traitor()

    # GAME END
    if session[0]:
        win_msg = win_condition()
        await end_game(win_msg[1], win_msg[2])


async def start_votes(player):
    start = datetime.now()
    while (datetime.now() - start).total_seconds() < 60:
        votes_needed = max(2, min(len(session[1]) // 4 + 1, 4))
        votes = len([x for x in session[1] if session[1][x][1] == "start"])
        if votes >= votes_needed or session[0] or votes == 0:
            break
        await asyncio.sleep(0.1)
    else:
        for player in session[1]:
            session[1][player][1] = ""
        await send_lobby("Not enough votes to start, resetting start votes.")


async def rate_limit(message):
    if (
        not (message.channel.is_private or message.content.startswith(BOT_PREFIX))
        or message.author.id in ADMINS
        or message.author.id == OWNER_ID
    ):
        return False
    global ratelimit_dict
    global IGNORE_LIST
    if message.author.id not in ratelimit_dict:
        ratelimit_dict[message.author.id] = 1
    else:
        ratelimit_dict[message.author.id] += 1
    if ratelimit_dict[message.author.id] > IGNORE_THRESHOLD:
        if message.author.id not in IGNORE_LIST:
            IGNORE_LIST.append(message.author.id)
            await log(
                2,
                message.author.name
                + " ("
                + message.author.id
                + ") was added to the ignore list for rate limiting.",
            )
        try:
            await reply(
                message,
                "You've used {0} commands in the last {1} seconds; I will ignore you from now on.".format(
                    IGNORE_THRESHOLD, TOKEN_RESET
                ),
            )
        except discord.Forbidden:
            await send_lobby(
                message.author.mention
                + " used {0} commands in the last {1} seconds and will be ignored from now on.".format(
                    IGNORE_THRESHOLD, TOKEN_RESET
                )
            )
        finally:
            return True
    if (
        message.author.id in IGNORE_LIST
        or ratelimit_dict[message.author.id] > TOKENS_GIVEN
    ):
        if ratelimit_dict[message.author.id] > TOKENS_GIVEN:
            await log(
                2,
                "Ignoring message from "
                + message.author.name
                + " ("
                + message.author.id
                + "): `"
                + message.content
                + "` since no tokens remaining",
            )
        return True
    return False
