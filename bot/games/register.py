from bot import bot

available_games = {}


def register_for_a_game(game_name: str, event):
    if not available_games.get(game_name):
        return False
    bot.current_games_dict.setdefault(game_name, {}).setdefault(
        event.chat.id, {}
    ).update(
        chat_id=event.chat.id, name=event.from_user.name, user_id=event.from_user.id
    )
    return True
