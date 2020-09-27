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

    async def manage_queens(
        self, queens: Optional[Units] = None, **queen_policy
    ) -> None:
        policy: Dict = self._read_queen_policy(**queen_policy)
        # print(policy)
        if queens is None:
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
        await self.creep.spread_creep(queens)

    async def spread_existing_tumors(self, tumors: Optional[Units]):
        await self.creep.spread_existing_tumors(tumors)

    async def inject_bases(self, queens: Units) -> None:
        pass

    def _assign_queen_roles(self) -> None:
        pass

    def _read_queen_policy(self, **queen_policy: Dict) -> Dict:
        """
        Read the queen policy the user passed in, add default
        params for missing values

        :param queen_policy:
        :type queen_policy: Dict
        :return: new policy with default params for missing values
        :rtype: Dict
        """
        creep_activated = queen_policy.get("creep_activated", True)
        distance_between_tumors = queen_policy.get("distance_between_tumors", 7)

        return {
            "creep_activated": creep_activated,
            "distance_between_tumors": distance_between_tumors,
        }
