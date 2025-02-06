from .roles import roles


class Player:
    def __init__(self, role, _id, user_id):
        teams = ["villager", "wolf", "nuetral"]
        for attr in teams:
            setattr(self, attr, False)
        for attr in list(roles.keys()):
            if roles.get(role)[0] not in teams:
                continue
            value = True if attr == role else False
            if value:
                team = roles.get(role)[0]
                setattr(self, team, value)
            setattr(self, attr.replace(" ", "_"), value)
        self.role = role
        self.description = roles.get(role)[2]
        self.lynched = False
        self.dead = False
        self.id = _id
        self.wa_id = user_id
        self.template = None
