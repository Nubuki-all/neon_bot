DETECTIVE_REVEAL_CHANCE = 0.4

# {role name : [team, plural, description]}
roles = {
    'wolf' : ['wolf', 'wolves', "Your job is to kill all of the villagers. Type `kill <player>` in private message to kill them."],
     'werecrow' : ['wolf', 'werecrows', "You are part of the wolfteam. Use `observe <player>` during the night to see if they were in bed or not. "
                                        "You may also use `kill <player>` to kill them."],
     'wolf cub' : ['wolf', 'wolf cubs', "You are part of the wolfteam. While you cannot kill anyone, the other wolves will "
                                        "become enraged if you die and will get two kills the following night."],
     'werekitten' : ['wolf', 'werekittens', "You are like a normal wolf, except due to your cuteness, you are seen as a villager "
                                            "and gunners will always miss when they shoot you. Use `kill <player>` in private message "
                                            "to vote to kill <player>."],
     'wolf shaman' : ['wolf', 'wolf shamans', "You are part of the wolfteam. You may use `kill <player>` to kill a villager. You can also select "
                                              "a player to receive a totem each night by using `give <player>.` You may give yourself a totem, "
                                              "but you may not give the same player a totem two nights in a row. If you do not give the totem "
                                              "to anyone, it will be given to a random player."],
     'traitor' : ['wolf', 'traitors', "You are exactly like a villager, but you are part of the wolf team. Only the detective can reveal your true "
                                      "identity. Once all other wolves die, you will turn into a wolf."],
     'sorcerer' : ['wolf', 'sorcerers', "You may use `observe <player>` in pm during the night to observe someone and determine if they "
                                        "are the seer, oracle, or augur. You are seen as a villager; only detectives can reveal your true identity."],
     'cultist' : ['wolf', 'cultists', "Your job is to help the wolves kill all of the villagers. But you do not know who the wolves are."],
     'seer' : ['villager', 'seers', "Your job is to detect the wolves; you may have a vision once per night. Type `see <player>` in private message to see their role."],
     'oracle' : ['villager', 'oracles', "Your job is to detect the wolves; you may have a vision once per night. Type `see <player>` in private message to see whether or not they are a wolf."],
     'shaman' : ['villager', 'shamans', "You select a player to receive a totem each night by using `give <player>`. You may give a totem to yourself, but you may not give the same"
                                       " person a totem two nights in a row. If you do not give the totem to anyone, it will be given to a random player. "
                                       "To see your current totem, use the command `myrole`."],
     'harlot' : ['villager', 'harlots', "You may spend the night with one player each night by using `visit <player>`. If you visit a victim of a wolf, or visit a wolf, "
                                       "you will die. You may visit yourself to stay home."],
     'hunter' : ['villager', 'hunters', "Your job is to help kill the wolves. Once per game, you may kill another player using `kill <player>`. "
                                       "If you do not wish to kill anyone tonight, use `pass` instead."],
     'augur' : ['villager', 'augurs', "Your job is to detect the wolves; you may have a vision once per night. Type `see <player>` in private message to see the aura they exude."
                                     " Blue is villager, grey is neutral, and red is wolf."],
     'detective' : ['villager', 'detectives', "Your job is to determine all of the wolves and traitors. During the day, you may use `id <player>` in private message "
                                             "to determine their true identity. However you risk a {}% chance of revealing your role to the wolves every time you use your ability.".format(int(DETECTIVE_REVEAL_CHANCE * 100))],
     'villager' : ['villager', 'villagers', "Your job is to lynch all of the wolves."],
     'crazed shaman' : ['neutral', 'crazed shamans', "You select a player to receive a random totem each night by using `give <player>`. You may give a totem to yourself, "
                                                     "but you may not give the same person a totem two nights in a row. If you do not give the totem to anyone, "
                                                     "it will be given to a random player. You win if you are alive by the end of the game."],
     'fool' : ['neutral', 'fools', "You become the sole winner if you are lynched during the day. You cannot win otherwise."],
     'cursed villager' : ['template', 'cursed villagers', "This template is hidden and is seen as a wolf by the seer. Roles normally seen as wolf, the seer, and the fool cannot be cursed."],
     'gunner' : ['template', 'gunners', ("This template gives the player a gun. Type `shoot <player>` in group during the day to shoot <player>."
                                        "If you are a villager and shoot a wolf, they will die. Otherwise, there is a chance of killing them, injuring "
                                        "them, or the gun exploding. If you are a wolf and shoot at a wolf, you will intentionally miss.")],
     'assassin' : ['template', 'assassins', "Choose a target with `target <player>`. If you die you will take out your target with you. If your target dies you may choose another one. "
                                            "Wolves and info-obtaining roles (such as seer and oracle) may not be assassin."],
     'matchmaker' : ['villager', 'matchmakers', "You can select two players to be lovers with `choose <player1> and <player2>`."
                                               " If one lover dies, the other will as well. You may select yourself as one of the lovers."
                                               " You may only select lovers during the first night."
                                               " If you do not select lovers, they will be randomly selected and you will not be told who they are (unless you are one of them)."],
     'guardian angel' : ['villager', 'guardian angels', "Your job is to protect the villagers. Use `guard <player>` in private message during night to protect "
                                                       "them from dying. You may protect yourself, however you may not guard the same player two nights in a row."],
     'jester' : ['neutral', 'jesters', "You will win alongside the normal winners if you are lynched during the day. You cannot otherwise win this game."],
     'minion' : ['wolf', 'minions', "It is your job to help the wolves kill all of the villagers. You are told who your leaders are on the first night, though they do not know you and you must tell them. Otherwise you have no powers, like a cultist"],
     'amnesiac' : ['neutral', 'amnesiacs', "You have forgotten your original role and need to wait a few nights to let the fog clear. You will win with the default role, until you remember your original role."],
     'blessed villager' : ['template', 'blessed villagers', "You feel incredibly safe. You won't be able to die as a normal villager, unless two players target you, or you are lynched at day."],
     'vengeful ghost' : ['neutral', 'vengeful ghosts', "Your soul will never be at rest. If you are killed during the game, you will swear eternal revenge upon team that killed you."
                                                       " Use `kill <player>` once per night after dying to kill an alive player. You only win if the team you swore revenge upon loses."],
     'priest' : ['villager', 'priests', "Once per game during the day, you may bless someone with `bless <player>` to prevent them from being killed. Furthermore, you may consecrate the dead during the day with `consecrate <player>` to settle down restless spirits and prevent the corpse from rising as undead that night; doing so removes your ability to participate in the vote that day."],
     'doomsayer' : ['wolf', 'doomsayers', "You can see how bad luck will befall someone at night by using `see <player>` on them. You may also use `kill <player>` to kill a villager."],
     'succubus' : ['neutral', 'succubi', "You may entrance someone and make them follow you by visiting them at night. If all alive players are entranced, you win. Use `visit <player>` to visit a player or `pass` to stay home. If you visit the victim of the wolves, you will die."],
     'mayor' : ['template', 'mayors', "If the mayor would be lynched during the day, they reveal that they are the mayor and nobody is lynched that day. A mayor that has previously been revealed will be lynched as normal."],
     'monster' : ['neutral', 'monsters', "You cannot be killed by the wolves. If you survive until the end of the game, you win instead of the normal winners."],
     'sharpshooter' : ['template', 'sharpshooters', "This template is like the gunner template but due to it's holder's skills, they may never miss their target."],
     'village drunk': ['villager', 'village drunks', "You have been drinking too much!"],
     'hag' : ['wolf', 'hags', "You can hex someone to prevent them from using any special powers they may have during the next day and night. Use `hex <player>` to hex them. Only detectives can reveal your true identity, seers will see you as a regular villager."],
     'bodyguard' : ['villager', 'bodyguards', "It is your job to protect the villagers. If you guard a victim, you will sacrifice yourself to save them. Use `guard <player>` to guard a player or `pass` to not guard anyone tonight."],
     'piper' : ['neutral', 'pipers', "You can select up to two players to charm each night. The charmed players will know each other, but not who charmed them. You win when all other players are charmed. Use `charm <player1> and <player2>` to select the players to charm, or `charm <player>` to charm just one player."],
     'warlock' : ['wolf', 'warlocks', "Each night you can curse someone with `curse <player>` to turn them into a cursed villager, so the seer sees them as wolf. Act quickly, as your curse applies as soon as you cast it! Only detectives can reveal your true identity, seers will see you as a regular villager."],
     'mystic' : ['villager', 'mystics', "Each night you will sense the number of evil villagers there are."],
     'wolf mystic' : ['wolf', 'wolf mystics', "Each night you will sense the number of villagers with a power that oppose you. You can also use `kill <player>` to kill a villager."],
     'mad scientist' : ['villager', 'mad scientists', "You win with the villagers, and should you die, you will let loose a potent chemical concoction that will kill the players next to you if they are still alive."],
     'clone' : ['neutral', 'clones', "You can select someone to clone with `clone <player>`. If that player dies, you become their role. You may only clone someone during the first night."],
     'lycan' : ['neutral', 'lycans', "You are currently on the side of the villagers, but will turn into a wolf instead of dying if you are targeted by the wolves during the night."],
     'time lord' : ['villager', 'time lords', "You are a master of time .. but you do not know it. If you are killed, day and night will speed up considerably."],
     'turncoat' : ['neutral', 'turncoats', "You can change the team you side with every other night. Use `side villagers` or `side wolves` to choose your team. If you do not wish to switch sides tonight, then you may use `pass`."],
     'serial killer' : ['neutral', 'serial killers', "You may kill one player each night with `kill <player>`. Your objective is to outnumber the rest of town. If there are any other serial killers, then you do not know who they are, but you win together, provided that the serial killer is alive. The wolves are unable to kill you at night. If you do not wish to kill anyone tonight, then you may use `pass`."],
     'executioner' : ['neutral', 'executioners', "At the start of the game, you will receive a target. This target is on the village team and your goal is to have this player lynched, while you are alive. If your target dies not via lynch, then you will become a jester."],
     'hot potato' : ['neutral', 'hot potatoes', "Under no circumstances may you win the game. You may choose to swap identities with someone else by using `choose <player>` at night."],
     'bishop' : ['template', 'bishops', "Your virtue prevents you from being entranced by the succubus."]
    
}

gamemodes = {
    'default' : {
        'description' : "The default gamemode.",
        'min_players' : 4,
        'max_players' : 24,
        'chance' : 30,
        'roles' : {
            #4, 5, 6, 7, 8, 9, 10,11,12,13,14,15,16,17,18,19,20,21,22,23,24
            'wolf' :
            [1, 1, 1, 1, 1, 1,  1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
            'werecrow' :
            [0, 0, 0, 0, 0, 0,  0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'wolf cub' :
            [0, 0, 0, 0, 0, 0,  1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'werekitten' :
            [0, 0, 0, 0, 0, 0,  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1],
            'traitor' :
            [0, 0, 0, 0, 1, 1,  1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1 ,1 ,1, 1],
            'hag' :
            [0, 0, 0, 0, 0, 0,  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1],
            'warlock' :
            [0, 0, 0, 0, 0, 0,  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            'cultist' :
            [0, 0, 0, 1, 0, 0,  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            'seer' :
            [1, 1, 1, 1, 1, 1,  1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'oracle' :
            [0, 0, 0, 0, 0, 0,  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1],
            'shaman' :
            [0, 0, 0, 1, 1, 1,  1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'harlot' :
            [0, 0, 0, 0, 1, 1,  1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'hunter' :
            [0, 0, 0, 0, 0, 0,  0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'augur' :
            [0, 0, 0, 0, 0, 0,  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1],
            'detective' :
            [0, 0, 0, 0, 0, 0,  0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
            'matchmaker' :
            [0, 0, 0, 0, 0, 0,  0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'bodyguard' :
            [0, 0, 0, 0, 0, 0,  0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1],
            'villager' :
            [2, 3, 4, 3, 3, 3,  3, 3, 3, 3, 4, 3, 3, 4, 4, 5, 4, 4, 5, 5, 5],
            'crazed shaman' :
            [0, 0, 0, 0, 0, 1,  1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'monster' :
            [0, 0, 0, 0, 0, 0,  0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'amnesiac' :
            [0, 0, 0, 0, 0, 0,  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1],
            'cursed villager' :
            [0, 0, 1, 1, 1, 1,  1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3],
            'gunner' :
            [0, 0, 0, 0, 0, 0,  1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'mayor' :
            [0, 0, 0, 0, 0, 0,  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1],
            'assassin' :
            [0, 0, 0, 0, 0, 0,  0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2]
        }
    },
#    'test' : {
#        'description' : "Gamemode for testing stuff.",
#        'min_players' : 5,
#        'max_players' : 23,
#        'roles' : {
#            #4, 5, 6, 7, 8, 9, 10,11,12,13,14,15,16,17,18,19,20,21,22,23,24
#            'wolf' :
#            [1, 1, 1, 1, 1, 1,  1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3],
#            'werecrow' :
#            [0, 0, 0, 0, 0, 0,  0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
#            'wolf cub' :
#            [0, 0, 0, 0, 0, 0,  1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
#            'traitor' :
#            [0, 0, 0, 0, 1, 1,  1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1 ,1 ,1, 1],
#            'sorcerer' :
#            [0, 0, 0, 0, 0, 0,  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1],
#            'cultist' :
#            [0, 0, 0, 1, 0, 0,  0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#            'seer' :
#            [1, 1, 1, 1, 1, 1,  1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
#            'shaman' :
#            [0, 0, 0, 1, 1, 1,  1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
#            'harlot' :
#            [0, 0, 0, 0, 1, 1,  1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
#            'hunter' :
#            [0, 0, 0, 0, 0, 0,  0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
#            'augur' :
#            [0, 0, 0, 0, 0, 0,  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1],
#            'detective' :
#            [0, 0, 0, 0, 0, 0,  0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
#            'matchmaker' :
#            [0, 0, 0, 0, 0, 0,  0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
#            'guardian angel' :
#            [0, 0, 0, 0, 0, 0,  0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1],
#            'villager' :
#            [2, 3, 4, 3, 3, 3,  3, 3, 2, 2, 3, 3, 2, 3, 3, 4, 3, 3, 4, 4, 4],
#            'crazed shaman' :
#            [0, 0, 0, 0, 0, 1,  1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2],
#            'amnesiac' :
#            [0, 0, 0, 0, 0, 0,  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1],
#            'cursed villager' :
#            [0, 0, 1, 1, 1, 1,  1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3],
#            'gunner' :
#            [0, 0, 0, 0, 0, 0,  1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2],
#            'assassin' :
#            [0, 0, 0, 0, 0, 0,  0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
#            'mayor' :
#            [0, 0, 0, 0, 0, 0,  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1],
#            'monster' :
#            [0, 0, 0, 0, 0, 0,  0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1],
#            'hag' :
#            [0, 0, 0, 0, 0, 0,  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]
#        }
#    },
    'foolish' : {
        'description' : "Watch out, because the fool is always there to steal the win.",
        'min_players' : 8,
        'max_players' : 24,
        'chance' : 10,
        'roles' : {
            #4, 5, 6, 7, 8, 9, 10,11,12,13,14,15,16,17,18,19,20,21,22,23,24
            'wolf' :
            [0, 0, 0, 0, 1, 1,  2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 4],
            'wolf cub' :
            [0, 0, 0, 0, 0, 0,  0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'traitor' :
            [0, 0, 0, 0, 1, 1,  1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2],
            'sorcerer' :
            [0, 0, 0, 0, 0, 0,  0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'oracle' :
            [0, 0, 0, 0, 1, 1,  1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'shaman' :
            [0, 0, 0, 0, 0, 0,  0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'harlot' :
            [0, 0, 0, 0, 1, 1,  1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2],
            'hunter' :
            [0, 0, 0, 0, 0, 1,  1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'augur' :
            [0, 0, 0, 0, 0, 0,  0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'bodyguard' :
            [0, 0, 0, 0, 0, 0,  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1],
            'villager' :
            [0, 0, 0, 0, 3, 3,  3, 2, 2, 3, 4, 3, 4, 3, 4, 5, 5, 5, 6, 7, 7],
            'clone' :
            [0, 0, 0, 0, 0, 0,  0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'fool' :
            [0, 0, 0, 0, 1, 1,  1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'cursed villager' :
            [0, 0, 0, 0, 1, 1,  1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'gunner' :
            [0, 0, 0, 0, 0, 0,  0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2]
        }
    },
    'chaos' : {
        'description' : "Chaotic and unpredictable. Any role, including wolves, can be a gunner.",
        'min_players' : 4,
        'max_players' : 16,
        'chance' : 0,
        'roles' : {
            #4, 5, 6, 7, 8, 9, 10,11,12,13,14,15,16
            #wolf team
            'wolf' :
            [1, 1, 1, 1, 0, 0,  0, 0, 0, 0, 0, 0, 0],
            'wolf cub' :
            [0, 0, 0, 0, 0, 0,  1, 1, 1, 1, 1, 1, 1],
            'wolf shaman' :
            [0, 0, 0, 0, 1, 1,  1, 1, 1, 1, 2, 2, 2],
            'werekitten' :
            [0, 0, 0, 0, 0, 0,  0, 0, 1, 1, 1, 1, 1],
            #~~vil~~ shaman team
            'shaman' :
            [3, 4, 4, 5, 5, 5,  5, 6, 6, 6, 6, 6, 7],
            'oracle' :
            [0, 0, 0, 0, 1, 1,  1, 1, 1, 1, 1, 1, 1],
            #neutrals
            'crazed shaman' :
            [0, 0, 0, 0, 0, 1,  1, 1, 1, 1, 1, 1, 1],
            'jester' :
            [0, 0, 1, 1, 1, 1,  1, 1, 1, 2, 2, 2, 2],
            'vengeful ghost' :
            [0, 0, 0, 0, 0, 0,  0, 0, 0, 0, 0, 1, 1],
            #templates
            'cursed villager' :
            [0, 0, 0, 0, 1, 1,  1, 1, 1, 1, 1, 1, 1],
            'gunner' :
            [1, 1, 1, 1, 1, 2,  2, 2, 3, 3, 3, 3, 3],
            'sharpshooter' :
            [1, 1, 1, 1, 1, 1,  1, 1, 1, 1, 1, 1, 1],
            'assassin' :
            [0, 0, 0, 0, 0, 1,  1, 2, 2, 2, 2, 2, 2]
        }
    },
    'orgy' : {
        'description' : "Be careful who you visit! ( ͡° ͜ʖ ͡°)",
        'min_players' : 4,
        'max_players' : 16,
        'chance' : 0,
        'roles' : {
            #4, 5, 6, 7, 8, 9, 10,11,12,13,14,15,16
            'wolf' :
            [1, 1, 1, 1, 1, 1,  2, 2, 2, 3, 3, 3, 3],
            'traitor' :
            [0, 0, 0, 0, 1, 1,  1, 1, 1, 1, 1, 2, 2],
            'harlot' :
            [3, 4, 4, 4, 3, 4,  3, 4, 5, 3, 4, 4, 4],
            'matchmaker' :
            [0, 0, 1, 1, 1, 1,  2, 2, 2, 3, 3, 3, 4],
            'crazed shaman' :
            [0, 0, 0, 0, 1, 1,  1, 1, 1, 2, 2, 2, 2],
            'fool' :
            [0, 0, 0, 1, 1, 1,  1, 1, 1, 1, 1, 1, 1],
            'cursed villager' :
            [0, 0, 0, 0, 0, 0,  0, 0, 0, 0, 0, 0, 0]
        }
    },
    'crazy' : {
        'description' : "A free for all with many unstable alignments.",
        'min_players' : 4,
        'max_players' : 16,
        'chance' : 0,
        'roles' : {
            #4, 5, 6, 7, 8, 9, 10,11,12,13,14,15,16
            'wolf' :
            [1, 1, 1, 1, 1, 1, 2, 2, 2, 3, 3, 3, 3],
            'turncoat' :
            [2, 2, 3, 3, 4, 4, 4, 4, 4, 4, 5, 5, 6],
            'crazed shaman' :
            [1, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3, 4, 4],
            'fool' :
            [0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1],
            'clone' :
            [0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1],
            'shaman' :
            [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1]
        }
    },
##    'crazy' : {
##        'description' : "Random totems galore.",
##        'min_players' : 4,
##        'max_players' : 16,
##        'chance' : 0,
##        'roles' : {
##            #4, 5, 6, 7, 8, 9, 10,11,12,13,14,15,16
##            'wolf' :
##            [1, 1, 1, 1, 1, 1,  1, 1, 2, 2, 1, 1, 2],
##            'traitor' :
##            [0, 0, 0, 0, 1, 1,  1, 1, 1, 1, 2, 2, 2],
##            'crazed shaman' :
##            [3, 4, 5, 6, 5, 6,  7, 7, 7, 8, 8, 9, 9],
##            'fool' :
##            [0, 0, 0, 0, 1, 1,  1, 2, 2, 2, 3, 3, 3],
##            'cursed villager' :
##            [0, 0, 0, 0, 0, 0,  0, 0, 0, 0, 0, 0, 0]
##        }
##    },
    'belunga' : {
        'description' : "Originally an april fool's joke, this gamemode is interesting, to say the least.",
        'min_players' : 4,
        'max_players' : 24,
        'chance' : 0,
        'roles' : {
        }
    },
    'valentines' : {
        'description' : "Love and death are in the air, as the default role is matchmaker.",
        # [8] wolf, wolf(2), matchmaker, matchmaker(2), matchmaker(3), matchmaker(4), matchmaker(5), matchmaker(6)
        # [9] matchmaker(7) [10] matchmaker(8) [11] matchmaker(9) [12] monster [13] wolf(3) [14] matchmaker(10) [15] matchmaker(11)
        # [16] matchmaker(12) [17] wolf(4) [18] mad scientist [19] matchmaker(13) [20] matchmaker(14) [21] wolf(5) [22] matchmaker(15) [23] matchmaker(16) [24] wolf(6)
        'min_players' : 8,
        'max_players' : 24,
        'chance' : 0,
        'roles' : {
            #4, 5, 6, 7, 8, 9, 10,11,12,13,14,15,16,17,18,19,20,21,22,23,24
            'wolf' :
            [0, 0, 0, 0, 2, 2,  2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 6],
            'matchmaker' :
            [0, 0, 0, 0, 6, 7,  8, 9, 9, 9,10,11,12,12,12,13,14,14,15,16,16],
            'mad scientist' :
            [0, 0, 0, 0, 0, 0,  0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1],
            'monster' :
            [0, 0, 0, 0, 0, 0,  0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
        }
    },
    'evilvillage' : {
        'description' : 'Majority of the village is wolf aligned, safes must secretly try to kill the wolves.',
        'min_players' : 6,
        'max_players' : 18,
        'chance' : 5,
        'roles' : {
            #4, 5, 6, 7, 8, 9, 10,11,12,13,14,15,16,17,18
            'wolf' :
            [0, 0, 1, 1, 1, 1,  1, 1, 1, 1, 1, 2, 2, 2, 2],
            'cultist' :
            [0, 0, 4, 5, 5, 6,  4, 5, 5, 6, 7, 6, 7, 8, 9],
            'seer' :
            [0, 0, 0, 0, 1, 1,  1, 1, 1, 1, 1, 1, 1, 1, 1],
            'shaman' :
            [0, 0, 0, 0, 0, 0,  0, 0, 1, 1, 1, 1, 1, 1, 1],
            'hunter' :
            [0, 0, 1, 1, 1, 1,  1, 1, 1, 1, 1, 2, 2, 2, 2],
            'guardian angel' :
            [0, 0, 0, 0, 0, 0,  1, 1, 1, 1, 1, 1, 1, 1, 1],
            'fool' :
            [0, 0, 0, 0, 0, 0,  1, 1, 1, 1, 1, 1, 1, 1, 1],
            'minion' :
            [0, 0, 0, 0, 0, 0,  1, 1, 1, 1, 1, 1, 1, 1, 1],
            'mayor' :
            [0, 0, 0, 0, 0, 0,  0, 0, 1, 1, 1, 1, 1, 1, 1]
        }
    },
    'drunkfire' : {
        'description' : "Most players get a gun, quickly shoot all the wolves!",
        'min_players' : 8,
        'max_players' : 17,
        'chance' : 0,
        'roles' : {
            # 4, 5, 6,7, 8, 9, 10,11,12,13,14,15,16,17
            'wolf' :
            [0, 0, 0, 0, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3],
            'traitor' :
            [0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2],
            'hag' :
            [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1],
            'seer' :
            [0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'village drunk' :
            [0, 0, 0, 0, 2, 2, 3, 3, 4, 4, 4, 4, 5, 5],
            'villager' :
            [0, 0, 0, 0, 3, 4, 3, 4, 2, 3, 3, 4, 3, 4],
            'crazed shaman' :
            [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1],
            'cursed villager' :
            [0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'gunner' :
            [0, 0, 0, 0, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9],
            'sharpshooter' :
            [0, 0, 0, 0, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4],
            'assassin' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1]
        }
    },
    'random' : {
        'description' : "Other than ensuring the game doesn't end immediately, no one knows what roles will appear.",
        'min_players' : 8,
        'max_players' : 20,
        'chance' : 0,
        'roles' : {
        }
    },
    'mudkip' : {
        'description' : "Why are all the professors named after trees?",
        'min_players' : 4,
        'max_players' : 15,
        'chance' : 5,
        'roles' : {
            'wolf' :
            [1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2],
            'wolf shaman' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1],
            'doomsayer' :
            [0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1],
            'minion' :
            [0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0],
            'shaman' :
            [0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1],
            'detective' :
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'guardian angel' :
            [0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'priest' :
            [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1],
            'villager' :
            [2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3],
            'jester' :
            [0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'amnesiac' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1],
            'vengeful ghost' :
            [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1],
            'succubus' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            'assassin' :
            [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1]
        }
    },
    'charming' : {
        'description' : "Charmed players must band together to find the piper in this game mode.",
        'min_players' : 6,
        'max_players' : 24,
        'chance' : 10,
         'roles' : {
            'seer' :
            [0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'harlot' :
            [0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'shaman' :
            [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2],
            'detective' :
            [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'bodyguard' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2],
            'wolf' :
            [0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 3, 3, 3],
            'traitor' :
            [0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'werekitten' :
            [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'warlock' :
            [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'sorcerer' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1],
            'piper' :
            [0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'vengeful ghost' :
            [0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'cursed villager' :
            [0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'gunner' :
            [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2],
            'mayor' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'assassin' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'villager' :
            [0, 0, 3, 4, 3, 4, 3, 3, 2, 3, 3, 4, 4, 5, 5, 5, 6, 7, 6, 7, 8]
         }
    },
    'mad' : {
        'description' : "This game mode has mad scientist and many things that may kill you.",
        'min_players' : 7,
        'max_players' : 22,
        'chance' : 5,
        'roles' : {
            #         7, 8, 9, 10,11,12,13,14,15,16,17,18,19,20,21,22,
            'villager' :
            [0, 0, 0, 4, 4, 5, 4, 5, 4, 5, 4, 4, 5, 4, 4, 5, 5, 6, 7],
            'seer' :
            [0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'mad scientist' :
            [0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'village drunk' :
            [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'detective' :
            [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'harlot' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1],
            'hunter' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1],
            # wolf team
            'wolf' :
            [0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2],
            'traitor' :
            [0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'werecrow' :
            [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'wolf cub' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 2, 2, 2],
            'cultist' :
            [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            # neutrals
            'jester' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1],
            'vengeful ghost' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            # templates
            'cursed villager' : 
            [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'gunner' :
            [0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'assassin' : 
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1]
        }
    },
    'lycan' : {
        'description' : "Many lycans will turn into wolves. Hunt them down before the wolves overpower the village.",
        'min_players' : 7,
        'max_players' : 21,
        'chance' : 5,
        'roles' : {
            #         7, 8, 9, 10,11,12,13,14,15,16,17,18,19,20,21
            'villager' :
            [0, 0, 0, 3, 3, 3, 1, 1, 1, 2, 3, 2, 3, 3, 4, 4, 4, 5],
            'seer' :
            [0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2],
            'bodyguard' :
            [0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'matchmaker' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1],
            'hunter' :
            [0, 0, 0, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
            # wolf team
            'wolf' :
            [0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'traitor' :
            [0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'wolf shaman' :
            [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            # neutrals
            'clone' :
            [0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2],
            'lycan' :
            [0, 0, 0, 1, 1, 1, 2, 2, 3, 3, 3, 4, 4, 4, 4, 4, 5, 5],
            # templates
            'cursed villager' : 
            [0, 0, 0, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
            'gunner' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1],
            'mayor' : 
            [0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
        }
    },
    'rapidfire' : {
        'description' : "Many killing roles and roles that cause chain deaths. Living has never been so hard.",
        'min_players' : 6,
        'max_players' : 24,
        'chance' : 0,
        'roles' : {
            #      6, 7, 8, 9, 10,11,12,13,14,15,16,17,18,19,20,21,22,23,24
            'villager' :
            [0, 0, 3, 4, 3, 4, 2, 3, 2, 3, 4, 2, 3, 4, 1, 2, 3, 4, 2, 3, 4],
            'seer' :
            [0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'mad scientist' :
            [0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2],
            'matchmaker' :
            [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2],
            'hunter' :
            [0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2],
            'augur' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'time lord' :
            [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2],
            # wolf team
            'wolf' :
            [0, 0, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4],
            'wolf cub' :
            [0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
            'traitor' :
            [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            # neutrals
            'vengeful ghost' :
            [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2],
            'amnesiac' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            # templates
            'cursed villager' : 
            [0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2],
            'gunner' :
            [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'sharpshooter' :
            [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'assassin' : 
            [0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2]
        }
    },
    'noreveal' : {
        'description' : "Roles are not revealed on death.",
        'min_players' : 4,
        'max_players' : 21,
        'chance' : 1,
        'roles' : {
            #4, 5, 6, 7, 8, 9, 10,11,12,13,14,15,16,17,18,19,20,21
            'villager' :
            [2, 3, 4, 5, 4, 5, 4, 5, 4, 5, 6, 4, 5, 4, 5, 5, 6, 7],
            'seer' :
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'guardian angel' :
            [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'mystic' :
            [0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'detective' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1],
            'hunter' :
            [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            # wolf team
            'wolf' :
            [1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3],
            'wolf mystic' :
            [0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'traitor' :
            [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'werecrow' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1],
            # neutrals
            'clone' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1],
            'lycan' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1],
            'amnesiac' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1],
            # templates
            'cursed villager' : 
            [0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2]
        }
    },
    'aleatoire' : {
        'description' : "Lots of roles to avoid killing who may not even know it themselves.",
        'min_players' : 8,
        'max_players' : 24,
        'chance' : 10,
        'roles' : {
            #4, 5, 6, 7, 8, 9, 10,11,12,13,14,15,16,17,18,19,20,21,22,23,24
            'villager' :
            [0, 0, 0, 0, 4, 5, 3, 4, 2, 3, 3, 2, 3, 2, 2, 3, 4, 3, 4, 5, 6],
            'seer' :
            [0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'shaman' :
            [0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'matchmaker' :
            [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'guardian angel' :
            [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'hunter' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1],
            'augur' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'time lord' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1],
            # wolf team
            'wolf' :
            [0, 0, 0, 0, 1, 1, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3],
            'wolf cub' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1],
            'traitor' :
            [0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'werecrow' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'hag' :
            [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            # neutrals
            'vengeful ghost' :
            [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2],
            'amnesiac' :
            [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'turncoat' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            # templates
            'cursed villager' : 
            [0, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
            'assassin' : 
            [0, 0, 0, 0, 0, 0, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
            'gunner' : 
            [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'mayor' : 
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
        }
    },
    'bloodbath' : {
        'description' : "A serial killer is on the loose...shall it end up on the noose?",
        'min_players' : 9,
        'max_players' : 24,
        'chance' : 0,
        'roles' : {
            #4, 5, 6, 7, 8, 9, 10,11,12,13,14,15,16,17,18,19,20,21,22,23,24
            # wolf team
            'wolf' :
            [0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
            'werecrow' :
            [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'traitor' :
            [0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'hag' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1],
            'cultist' :
            [0, 0, 0, 0, 0, 0, 1, 1, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 1, 1, 1],
            # village team
            'seer' :
            [0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'oracle' :
            [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'shaman' :
            [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2],
            'hunter' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'guardian angel' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1],
            'bodyguard' :
            [0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'priest' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1],
            'villager' :
            [0, 0, 0, 0, 0, 4, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
            # neutrals
            'amnesiac' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            'vengeful ghost' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1],
            'clone' :
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1],
            'turncoat' :
            [0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'serial killer' :
            [0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
            # templates
            'gunner' : 
            [0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4]
        }
    }
#    'template' : {
#        'description' : "This is a template you can use for making your own gamemodes.",
#        'min_players' : 0,
#        'max_players' : 0,
#        'roles' : {
#            #4, 5, 6, 7, 8, 9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24
#            'wolf' :
#            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#            'werecrow' :
#            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#            'wolf cub' :
#            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#            'werekitten' :
#            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#            'traitor' :
#            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#            'sorcerer' :
#            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#            'cultist' :
#            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#            'seer' :
#            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#            'oracle' :
#            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#            'shaman' :
#            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#            'harlot' :
#            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#            'hunter' :
#            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#            'augur' :
#            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#            'detective' :
#            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#            'matchmaker' :
#            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#            'guardian angel' :
#            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#            'villager' :
#            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#            'jester' :
#            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#            'fool' :
#            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#            'crazed shaman' :
#            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#            'amnesiac' :
#            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#            'cursed villager' :
#            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#            'gunner' :
#            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#            'assassin' :
#            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#            'minion' :
#            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#            'monster' :
#            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#            'mayor' :
#            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
#            'hag' :
#            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
#        }
#    }
}