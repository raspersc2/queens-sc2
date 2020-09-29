from typing import Dict

from sc2 import BotAI
from sc2.units import Units


class Creep:
    def __init__(self, bot: BotAI, creep_policy: Dict):
        self.bot: BotAI = bot
        self.creep_policy: Dict = creep_policy

    async def spread_creep(self, queens: Units) -> None:
        pass

    async def spread_existing_tumors(self, tumors: Units):
        pass
