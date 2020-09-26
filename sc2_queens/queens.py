from typing import Dict, List, Optional

from sc2 import BotAI
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.position import Point2
from sc2.units import Units

from sc2_queens.creep import Creep
from sc2_queens.defence import Defence
from sc2_queens.inject import Inject


class Queens:
    def __init__(self, bot: BotAI):
        self.bot: BotAI = bot
        self.creep: Creep = Creep(bot)
        self.defence: Defence = Defence(bot)
        self.inject: Inject = Inject(bot)

        self.defence_queen_tags: List[int]
        self.inject_targets: Dict

    async def auto_queen(self, queens: Optional[Units]) -> None:
        queens: Units = self.bot.units(UnitID.QUEEN)
        for queen in queens:
            queen.attack(self.bot.enemy_start_locations[0])

    async def handle_defence(self, queens: Units) -> None:
        pass

    async def spread_creep(
        self,
        queens: Units,
        safe_location: Optional[Point2],
        should_retreat: bool = True,
    ) -> None:
        pass

    async def inject_bases(self, queens: Units) -> None:
        pass

    def _assign_queen_roles(self) -> None:
        pass
