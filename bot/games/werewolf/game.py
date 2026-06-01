import math
import random
from datetime import datetime

from bot.config import bot

from .defaults import (
    DEFAULT_DAY_TIMEOUT,
    DEFAULT_DAY_WARNING,
    DEFAULT_NIGHT_TIMEOUT,
    DEFAULT_NIGHT_WARNING,
    GUNNER_MULTIPLIER,
    MIN_PLAYERS,
    SHARPSHOOTER_MULTIPLIER,
    WOLFCHAT_ROLES,
)
from .player import Player
from .roles import gamemodes, roles


class Game:
    def __init__(self, event, mode=None):
        self.game_id = 0
        self.chat_id = event.chat.id
        self.chat_jid = event.chat.jid

        self.requested_mode = mode
        self.mode = mode or "default"

        self.player_ids = [event.from_user.id]
        self.player_names = {event.from_user.id: event.from_user.name}
        self.players = {}  # user_id: Player object
        self.newly_killed = []  # user_ids

        self.day = False
        self.night = False
        self.waiting = True
        self.in_progress = False
        self.restricted = False

        self.start_time = None
        self.night_start_time = None
        self.day_start_time = None

        self.night_num = 0
        self.detective_acted = False

        self.day_warning = DEFAULT_DAY_WARNING
        self.day_timeout = DEFAULT_DAY_TIMEOUT
        self.night_warning = DEFAULT_NIGHT_WARNING
        self.night_timeout = DEFAULT_NIGHT_TIMEOUT

    def select_mode_by_chance(self):
        if self.requested_mode:
            return self.requested_mode
        available_modes = []
        chances = []
        for m, data in gamemodes.items():
            if data.get("chance", 0) > 0 and self.total_players >= data.get(
                "min_players", MIN_PLAYERS
            ):
                available_modes.append(m)
                chances.append(data["chance"])
        if not available_modes:
            return "default"
        return random.choices(available_modes, weights=chances, k=1)[0]

    @property
    def min_players(self):
        if self.requested_mode:
            return gamemodes[self.requested_mode].get("min_players", MIN_PLAYERS)
        return MIN_PLAYERS

    @property
    def total_players(self):
        return len(self.player_ids)

    @property
    def players_alive_list(self):
        return [p for p in self.players.values() if p.is_alive]

    @property
    def players_alive_count(self):
        return len(self.players_alive_list)

    def get_player_by_id(self, p_id):
        for p in self.players.values():
            if str(p.id) == str(p_id):
                return p
        return None

    def get_player_by_user_id(self, user_id):
        return self.players.get(user_id)

    def set_each_role_numbers_and_pool(self):
        self.mode = self.select_mode_by_chance()
        mode_data = gamemodes.get(self.mode)
        self.role_pool = []
        self.template_pool = []
        idx = self.total_players - 4
        for role_name, counts in mode_data.get("roles", {}).items():
            if idx < 0:
                count = counts[0] if counts else 0
            else:
                count = counts[idx] if idx < len(counts) else counts[-1]
            if count <= 0:
                continue
            if roles.get(role_name)[0] == "template":
                for _ in range(count):
                    self.template_pool.append(role_name)
            else:
                for _ in range(count):
                    self.role_pool.append(role_name)

    def assign_roles(self):
        while not self.game_id:
            _id = random.randint(1000, 9980)
            if _id not in bot.current_games_dict.get("werewolf_ids", []):
                self.game_id = _id
                bot.current_games_dict.setdefault("werewolf_ids", []).append(_id)

        to_assign = list(self.player_ids)
        random.shuffle(to_assign)
        random.shuffle(self.role_pool)

        while len(self.role_pool) < len(to_assign):
            self.role_pool.append("villager")

        for i, user_id in enumerate(to_assign):
            role = self.role_pool[i]
            player_name = self.player_names.get(user_id, "Unknown")
            player = Player(role, i + 1, user_id, player_name)
            self.players[user_id] = player

        for template in self.template_pool:
            eligible_players = [
                p for p in self.players.values() if template not in p.templates
            ]
            random.shuffle(eligible_players)
            for player in eligible_players:
                if template == "cursed villager":
                    if player.role in ["wolf", "seer", "fool"]:
                        continue
                elif template == "assassin":
                    if player.role in ["wolf", "oracle", "seer"]:
                        continue
                elif template in ["mayor", "bishop"]:
                    if player.team != "villager":
                        continue

                player.templates.append(template)
                if template == "gunner":
                    player.bullet_count = math.ceil(
                        self.total_players * GUNNER_MULTIPLIER
                    )
                elif template == "sharpshooter":
                    player.bullet_count = math.ceil(
                        self.total_players * SHARPSHOOTER_MULTIPLIER
                    )
                break

        self.in_progress = True
        self.waiting = False
        self.start_time = datetime.now()

    async def send_lobby(self, message):
        await bot.client.send_message(self.chat_jid, message)

    async def wolfchat(self, message):
        for p in self.players.values():
            if p.is_alive and p.role in WOLFCHAT_ROLES:
                try:
                    await bot.client.send_message(p.user_id, f"[WOLFCHAT] {message}")
                except Exception:
                    pass

    async def join(self, event, notify=False):
        if not self.waiting:
            return await event.reply("The game has already started!")
        if event.from_user.id in self.player_ids:
            return await event.reply("You've already joined the game!")
        if len(self.player_ids) >= 24:
            return await event.reply("The game is full!")
        self.player_ids.append(event.from_user.id)
        self.player_names[event.from_user.id] = event.from_user.name
        return (
            await event.reply(
                f"{event.from_user.name} has joined the game. ({self.total_players}/24)"
            )
            if not notify
            else await event.reply(
                f"@{event.user.id} has joined the game. ({self.total_players}/24)",
                quote=False,
            )
        )

    async def leave(self, event, notify=False):
        if not self.waiting:
            return await event.reply("The game has already started!")
        if event.from_user.id not in self.player_ids:
            return await event.reply("You've not joined the game!")
        del self.player_ids[event.from_user.id]
        self.player_names.pop(event.from_user.id)
        return (
            await event.reply(
                f"{event.from_user.name} has left the game. ({self.total_players}/24)"
            )
            if not notify
            else await event.reply(
                f"@{event.user.id} has left the game. ({self.total_players}/24)",
                quote=False,
            )
        )

    async def status(self, event):
        if self.waiting:
            msg = f"*Werewolf Game Lobby*\n"
            msg += f"Mode: {self.requested_mode or 'Auto (by chance)'}\n"
            msg += f"Players: {self.total_players}\n"
            msg += "*Joined players:*\n"
            for p_id in self.player_ids:
                name = self.player_names.get(p_id, "Unknown")
                msg += f"- {name}\n"
            await event.reply(msg)
        else:
            msg = f"*Werewolf Game Status ({self.mode})*\n"
            msg += f"Players alive: {self.players_alive_count}/{len(self.players)}\n"
            msg += f"Phase: {'Day' if self.day else 'Night'}\n"
            msg += f"Restricted: {self.restricted}\n"
            msg += "*Players:*\n"
            for p in self.players.values():
                status = "💀" if not p.is_alive else "🟢"
                msg += f"{status} {p.name} (#{p.id})\n"
            await event.reply(msg)

    async def check_traitor(self):
        wolves = [
            p
            for p in self.players_alive_list
            if p.team == "wolf" and p.role != "traitor"
        ]
        if not wolves:
            traitors = [p for p in self.players_alive_list if p.role == "traitor"]
            for t in traitors:
                t.role = "wolf"
                t.team = "wolf"
                await bot.client.send_message(
                    t.user_id,
                    "All other wolves are dead! You have turned into a *wolf*!",
                )
                await self.wolfchat(f"{t.name} has turned into a wolf!")
