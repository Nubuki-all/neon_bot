from .roles import roles


class Player:
    def __init__(self, role, _id, user_id, name):
        self.role = role  # Current role name
        self.original_role = role
        self.team = roles.get(role)[0]
        self.description = roles.get(role)[2]
        self.id = _id  # In-game numeric ID
        self.user_id = user_id  # WhatsApp JID
        self.name = name

        self.is_alive = True
        self.is_injured = False
        self.is_lynched = False

        self.templates = []  # e.g., ["gunner", "cursed"]
        # List of strings for various states (compatibility with original
        # logic)
        self.other = []

        self.target = ""  # Night target
        self.vote = ""  # Day vote

        # Specific role variables
        self.totem = ""  # Totem to give (Shaman)
        self.bullet_count = 0
        self.last_target = ""
        self.loves = []  # List of user_ids
        self.cloning_target = None
        self.execution_target = None
        self.side = "villagers" if self.team == "villager" else "wolves"
        self.hexed = False
        self.sick = False
        self.is_cursed = False
        self.is_blessed = False
        self.is_guarded = False
        self.is_entranced = False
        self.is_charmed = False

    @property
    def display_role(self):
        # Detective sees true identity, Seer sees cursed villager as wolf
        if "cursed villager" in self.templates:
            return "wolf" if self.role == "villager" else self.role
        return self.role

    @property
    def actual_team(self):
        # logic for turncoat, etc.
        if self.role == "turncoat":
            return "wolf" if "side:wolves" in self.other else "village"
        return self.team

    def add_other(self, state):
        if state not in self.other:
            self.other.append(state)

    def remove_other(self, state):
        if state in self.other:
            self.other.remove(state)

    def __repr__(self):
        return f"<Player {self.name} (#{self.id}) as {self.role}>"
