from typing import Dict
from sc2 import BotAI


class Defence:
    def __init__(self, bot: BotAI, defence_policy: Dict):
        self.bot: BotAI = bot
