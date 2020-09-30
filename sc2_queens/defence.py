from typing import Dict
from sc2 import BotAI

from sc2_queens.base_unit import BaseUnit


class Defence(BaseUnit):
    def __init__(self, bot: BotAI, defence_policy: Dict):
        super().__init__(bot)
