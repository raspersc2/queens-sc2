from typing import Dict

from sc2 import BotAI
from sc2.units import Units

from sc2_queens.base_unit import BaseUnit


class Creep(BaseUnit):
    def __init__(self, bot: BotAI, creep_policy: Dict):
        super().__init__(bot)
        self.creep_policy: Dict = creep_policy

    async def spread_creep(self, queens: Units) -> None:
        pass

    async def spread_existing_tumors(self, tumors: Units):
        pass
