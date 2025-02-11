import random

from bot.config import bot

from .defaults import (
    DEFAULT_DAY_TIMEOUT,
    DEFAULT_DAY_WARNING,
    DEFAULT_NIGHT_TIMEOUT,
    DEFAULT_NIGHT_WARNING,
)
from .player import Player
from .roles import gamemodes, roles


class Game:
    def __init__(self, event, mode="default"):
        self.id = 0
        self.chat_id = event.chat.id
        self.chat_jid = event.chat.jid
        self.total_players = 1
        self.mode = mode
        mode = gamemodes.get(self.mode)
        self.min_players = mode["min_players"]
        self.max_players = mode["max_players"]
        self.wolf_num = 0
        self.neutral_num = 0
        self.villager_num = 0

        self.player_ids = [event.from_user.id]
        self.players = {}  # id: Chracter object
        self.players_alive = 0
        self.newly_killed = []  # ids

        self.day = False
        self.night = False
        self.waiting = True

        # set defaults
        # self.wait_bucket = WAIT_BUCKET_INIT
        # self.wait_timer = datetime.now()
        self.day_warning = DEFAULT_DAY_WARNING
        self.day_timeout = DEFAULT_DAY_TIMEOUT
        self.night_warning = DEFAULT_NIGHT_WARNING
        self.night_timeout = DEFAULT_NIGHT_TIMEOUT

    def set_each_role_numbers_and_pool(self):
        pool = []
        t_pool = []
        mode = gamemodes.get(self.mode)
        for role in list(mode.get("roles").keys()):
            if (team := roles.get(role)[0]) != "template":
                value = mode.get("roles").get(role)[self.total_players - 4]
                if value:
                    setattr(self, role.replace(" ", "_") + "_unassigned", value)
                    prev_value = getattr(self, team + "_num")
                    setattr(self, team + "_num", prev_value + value)
                    setattr(self, role.replace(" ", "_") + "_num", value)
                    setattr(self, "_" + role.replace(" ", "_") + "_num", value)
                    pool.append(role)
            else:
                value = mode.get("roles").get(role)[self.total_players - 4]
                if value:
                    t_pool.append(role)
        self.role_pool = pool
        self.template_pool = t_pool

    def pre_assign_vars(self):
        self.charmed_num = 0
        self.entranced_num = 0

    def assign(self, ids):
        while not self.id:
            _id = gen_rand_4_digits()
            ids = expand(_id, self.total_players)
            if all(
                x
                not in bot.current_games_dict.setdefault("werewolf", {}).get("ids", [])
                for x in ids
            ):
                pass
            else:
                continue
            self.id = _id
            bot.current_games_dict.setdefault("werewolf", {}).setdefault(
                "ids", []
            ).extend(ids)

        _id = self.id
        to_be_assgined = list(self.player_ids)
        while len(to_be_assgined) != 0:
            random.shuffle(self.role_pool)
            _id += 1
            user_id = to_be_assgined[0]
            role = self.role_pool[0]
            player = Player(role, _id, user_id)
            self.players.update({user_id: player})
            value = getattr(self, role + "_unassigned")
            value -= 1
            if not value:
                self.role_pool.pop(0)
            setattr(self, role + "_unassigned", value)
            to_be_assgined.pop(0)
        for template in template_pool:
            player_list = list(self.players.values())
            random.shuffle(player_list)
            for player in player_list:
                if template.endswith("villager"):
                    if not player.villager:
                        continue
                    if template == "cursed villager" and not (
                        player.seer or player.fool
                    ):
                        pass
                    elif template == "cursed villager":
                        continue
                elif template == "assassin":
                    if player.wolf or player.oracle or player.seer:
                        continue
                elif template in ("mayor", "bishop"):
                    if not player.villager:
                        continue
                player.template = template
                setattr(player, template.replace(" ", "_"), True)
                break

    async def join(self, event):
        if (user_id := event.from_user.id) in self.player_ids:
            return await event.reply("You've lready joined the game!")
        self.player_ids.append(user_id)
        return await event.reply("You've successfully joined the game.")

    async def status(self, message):
        player_ids = list()
        while self.waiting:
            if self.player_ids == player_ids:
                await asyncio.sleep(10)
                continue
            player_ids = list(self.player_ids)
            msg = "*List of joined players:*"
            for p_id in player_ids:
                msg += f"- @{p_id}"
            await message.edit(msg)


def expand(num: int, amount: int):
    return [num + x for x in range(1, amount + 1)]


def gen_rand_4_digits():
    return random.randint(1000, 9980)
