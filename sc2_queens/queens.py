from typing import Callable, Dict, List, Optional

from sc2 import BotAI
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from sc2_queens.consts import QueenRoles
from sc2_queens.creep import Creep
from sc2_queens.defence import Defence
from sc2_queens.inject import Inject


class Queens:
    def __init__(self, bot: BotAI, **queen_policy: Dict):
        self.bot: BotAI = bot
        self.creep_queen_tags: List[int] = []
        self.defence_queen_tags: List[int] = []
        self.inject_targets: Dict[int, int] = {}
        self.queen_policy: Dict = self._read_queen_policy(**queen_policy)
        self.creep: Creep = Creep(bot, self.queen_policy["creep_queens"])
        self.defence: Defence = Defence(bot, self.queen_policy["defence_queens"])
        self.inject: Inject = Inject(bot, self.queen_policy["inject_queens"])

    async def manage_queens(self, queens: Optional[Units] = None) -> None:
        if queens is None:
            queens: Units = self.bot.units(UnitID.QUEEN)

        for queen in queens:
            self._assign_queen_role(queen)

    def remove_queen(self, unit_tag) -> None:
        pass

    async def handle_defence(self, queens: Units) -> None:
        pass

    async def spread_creep(self, queens: Units) -> None:
        await self.creep.spread_creep(queens)

    async def spread_existing_tumors(self, tumors: Optional[Units]):
        await self.creep.spread_existing_tumors(tumors)

    async def inject_bases(self, queens: Units) -> None:
        pass

    def _assign_queen_role(self, queen: Unit) -> None:
        """
        If queen does not have role, work out from the policy
        what role it should have
        :param queen:
        :type queen:
        :return:
        :rtype:
        """
        if self._queen_has_role(queen):
            return
        # if there are priority clashes, default is:
        # inject, creep, defence
        new_role: QueenRoles = QueenRoles.Inject
        for key, values in self.queen_policy.items():
            pass

    def _queen_has_role(self, queen: Unit) -> bool:
        """
        Checks if we know about queen, if not assign a role
        """
        queen_tag: List[int] = [
            tag
            for tag in [
                self.creep_queen_tags,
                self.defence_queen_tags,
                self.inject_targets.values(),
            ]
            if queen.tag in tag
        ]
        return len(queen_tag) > 0

    def _read_queen_policy(self, **queen_policy: Dict) -> Dict:
        """
        Read the queen policy the user passed in, add default
        params for missing values

        :param queen_policy:
        :type queen_policy: Dict
        :return: new policy with default params for missing values
        :rtype: Dict
        """

        return {
            "creep_queens": {
                "active": queen_policy.get("creep_queens", {}).get("active", True),
                "max": queen_policy.get("creep_queens", {}).get("max", 6),
                "priority": queen_policy.get("creep_queens", {}).get("priority", False),
                "defend_against_air": queen_policy.get("creep_queens", {}).get(
                    "defend_against_air", True
                ),
                "defend_against_ground": queen_policy.get("creep_queens", {}).get(
                    "defend_against_ground", True
                ),
                "tumors_block_expansions": queen_policy.get("creep_queens", {}).get(
                    "tumors_block_expansions", False
                ),
                "distance_between_tumors": queen_policy.get("creep_queens", {}).get(
                    "distance_between_tumors", 7
                ),
                "spread_till": queen_policy.get("creep_queens", {}).get(
                    "spread_till",
                    lambda: self.bot.structures(UnitID.CREEPTUMORBURROWED).amount > 15,
                ),
            },
            "defence_queens": {
                "active": queen_policy.get("defence_queens", {}).get("active", True),
                "max": queen_policy.get("defence_queens", {}).get("max", 3),
                "priority": queen_policy.get("defence_queens", {}).get(
                    "priority", False
                ),
                "defend_against_air": queen_policy.get("defence_queens", {}).get(
                    "defend_against_air", True
                ),
                "defend_against_ground": queen_policy.get("defence_queens", {}).get(
                    "defend_against_ground", True
                ),
                "rally_point": queen_policy.get("defence_queens", {}).get(
                    "rally_point",
                    self.bot.main_base_ramp.bottom_center.towards(
                        self.bot.game_info.map_center, 3
                    ),
                ),
            },
            "inject_queens": {
                "active": queen_policy.get("inject_queens", {}).get("active", True),
                "max": queen_policy.get("inject_queens", {}).get("max", 6),
                "priority": queen_policy.get("defence_queens", {}).get(
                    "priority", True
                ),
                "defend_against_air": queen_policy.get("inject_queens", {}).get(
                    "defend_against_air", False
                ),
                "defend_against_ground": queen_policy.get("inject_queens", {}).get(
                    "defend_against_ground", False
                ),
            },
        }
