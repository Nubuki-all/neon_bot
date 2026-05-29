MIN_PLAYERS = 4
MAX_PLAYERS = 24

RETRY_RUN_GAME = 3

PLAYER_TIMEOUT = 300
PLAYER_TIMEOUT2 = 60

DEFAULT_DAY_WARNING = 540
DEFAULT_DAY_TIMEOUT = 600
DEFAULT_NIGHT_WARNING = 90
DEFAULT_NIGHT_TIMEOUT = 120

EXTRA_WAIT = 30
WAIT_AFTER_JOIN = 15
WAIT_BUCKET_INIT = 1
WAIT_BUCKET_DELAY = 240
WAIT_BUCKET_MAX = 3

NOTIFY_COOLDOWN = 180

GAME_START_TIMEOUT = 60 * 30  # 30 minutes
QUIT_GAME_STASIS = 2

GUNNER_MISS = 1
GUNNER_SUICIDE = 1
GUNNER_HEADSHOT = 2
GUNNER_INJURE = 3
DRUNK_MISS = 3
DRUNK_SUICIDE = 2
DRUNK_HEADSHOT = 2
DRUNK_INJURE = 2
GUNNER_MULTIPLIER = 0.12  # bullets = ceil(num players * multiplier)
SHARPSHOOTER_MULTIPLIER = 0.06
DRUNK_MULTIPLIER = 3
GUNNER_REVENGE_WOLF = 0.25  # chance that gunner will kill wolf

DETECTIVE_REVEAL_CHANCE = 0.4

ACTUAL_WOLVES = [
    "wolf",
    "werecrow",
    "wolf cub",
    "werekitten",
    "wolf shaman",
    "doomsayer",
    "hag",
    "warlock",
    "wolf mystic",
]

WOLFCHAT_ROLES = ACTUAL_WOLVES + ["traitor", "sorcerer", "minion"]

COMMANDS_FOR_ROLE = {
    "kill": ACTUAL_WOLVES + ["serial killer", "hunter", "vengeful ghost"],
    "see": ["seer", "oracle", "augur", "doomsayer"],
    "give": ["shaman", "wolf shaman", "crazed shaman"],
    "visit": ["harlot", "succubus"],
    "guard": ["guardian angel", "bodyguard"],
    "observe": ["werecrow", "sorcerer"],
    "id": ["detective"],
}

lang = {
    "nokills": [
        "The night was quiet. Everyone is safe.",
        "Nobody died last night.",
        "The villagers awaken to a peaceful morning.",
    ],
    "lynched": [
        "The village has decided to lynch **{}**, a **{}**.",
        "**{}** was dragged to the gallows and revealed to be a **{}**.",
        "After much debate, the villagers lynch **{}**. They were a **{}**.",
    ],
    "lynchednoreveal": [
        "The village has decided to lynch **{}**.",
        "**{}** was dragged to the gallows.",
    ],
    "hastotem": ["**{}** has a totem!"],
    "hastotem2": ["**{}** and **{}** have totems!"],
    "hastotems": ["**{}**, and **{}** have totems!"],
}

SHAMAN_TOTEMS = [
    "protection_totem",
    "death_totem",
    "revealing_totem",
    "influence_totem",
    "impatience_totem",
    "pacifism_totem",
    "desperation_totem",
]

WOLF_SHAMAN_TOTEMS = [
    "protection_totem",
    "misdirection_totem",
    "deceit_totem",
    "lycanthropy_totem",
]
