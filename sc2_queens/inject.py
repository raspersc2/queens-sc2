from typing import Dict
from sc2 import BotAI


class Inject:
    def __init__(self, bot: BotAI, inject_policy: Dict):
        self.bot: BotAI = bot
