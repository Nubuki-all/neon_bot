from .roles import roles


class Player:
    def __init__(self, role, _id, user_id, name):
        self.role = role  # Current role name
        self.original_role = role
        self.team = roles.get(role)[0]
        self.description = roles.get(role)[2]
        self.id = _id  # In-game ID (numeric 1, 2, 3...)
        # WhatsApp user ID (e.g. "123456789@s.whatsapp.net")
        self.user_id = user_id
        self.name = name

        self.is_dead = False
        self.is_injured = False
        self.is_lynched = False

        self.templates = []  # e.g. ["gunner", "cursed villager"]
        # To store things like 'charmed', 'entranced', 'hexed', 'sick', etc.
        self.other_data = []
        self.target = ""  # Night target (user_id)
        self.vote = ""  # Day vote target (user_id)
        self.totem = ""  # Shaman totem to give or received totem
        self.bullet_count = 0

        self.last_target = ""  # For shaman/GA restriction

        # Special state variables
        self.loves = None  # user_id of lover
        self.cloning_target = None  # user_id
        self.executioner_target = None  # user_id
        self.side = "villagers" if self.team == "villager" else "wolves"  # For turncoat

    @property
    def is_alive(self):
        return not self.is_dead

    @property
    def is_wolf_aligned(self):
        # Wolves, minions, cultists (in some modes), and entranced players
        if "entranced" in self.other_data:
            return True
        if self.role in [
            "wolf",
            "werecrow",
            "wolf cub",
            "werekitten",
            "wolf shaman",
            "traitor",
            "sorcerer",
            "cultist",
            "minion",
            "doomsayer",
            "hag",
            "warlock",
            "wolf mystic",
        ]:
            return True
        return False

    @property
    def display_role(self):
        # Seer sees cursed villager as wolf
        if "cursed villager" in self.templates:
            return "wolf" if self.role == "villager" else self.role
        return self.role

    def add_other(self, data):
        if data not in self.other_data:
            self.other_data.append(data)

    def remove_other(self, data):
        if data in self.other_data:
            self.other_data.remove(data)

    def __repr__(self):
        return f"<Player {self.name} ({self.role})>"
