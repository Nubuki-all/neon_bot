from bot import bot

available_games = {"werewolf": True}


def register_for_a_game(game_name: str, event):
    if not available_games.get(game_name):
        return False

    current_games = bot.current_games_dict.setdefault(game_name, {})
    game = current_games.get(event.chat.id)

    if game:
        if hasattr(game, "waiting"):
            if not game.waiting:
                return "started"
        elif isinstance(game, dict) and game.get("started"):
             return "started"

    # If we are just checking if we can proceed with commands
    return True

def add_player_to_game(game_name: str, event):
    # This matches the user's original intent for registration
    bot.current_games_dict.setdefault(game_name, {}).setdefault(
        event.chat.id, {} # This will be replaced by Game object later or used as info
    )
    # If Game object exists, it should handle its own player list,
    # but we can keep this for compatibility if needed.
    return True
