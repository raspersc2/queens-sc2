from typing import Callable, Dict, List, Optional, Set

from sc2 import BotAI
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from sc2_queens.consts import QueenRoles
from sc2_queens.creep import Creep
from sc2_queens.defence import Defence
from sc2_queens.inject import Inject
from sc2_queens.policy import DefenceQueen, CreepQueen, InjectQueen, Policy

CREEP_POLICY: str = "creep_policy"
DEFENCE_POLICY: str = "defence_policy"
INJECT_POLICY: str = "inject_policy"


class Queens:
    def __init__(self, bot: BotAI, **queen_policy: Dict):
        self.bot: BotAI = bot
        self.creep_queen_tags: List[int] = []
        self.defence_queen_tags: List[int] = []
        self.inject_targets: Dict[int, int] = {}
        self.policies: Dict[str, Policy] = self._read_queen_policy(**queen_policy)
        self.creep: Creep = Creep(bot, self.policies[CREEP_POLICY])
        self.defence: Defence = Defence(bot, self.policies[DEFENCE_POLICY])
        self.inject: Inject = Inject(bot, self.policies[INJECT_POLICY])

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

    def set_new_policy(self, reset_roles: bool = True, **queen_policy) -> None:
        self.policies = self._read_queen_policy(**queen_policy)
        if reset_roles:
            self.creep_queen_tags = []
            self.defence_queen_tags = []
            self.inject_targets = {}

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
        # for key, values in self.queen_policy.items():
        #     pass

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

    def _read_queen_policy(self, **queen_policy: Dict) -> Dict[str, Policy]:
        """
        Read the queen policy the user passed in, add default
        params for missing values

        :param queen_policy:
        :type queen_policy: Dict
        :return: new policy with default params for missing values
        :rtype: Dict
        """
        cq_policy = queen_policy.get("creep_queens", {})
        dq_policy = queen_policy.get("defence_queens", {})
        iq_policy = queen_policy.get("inject_queens", {})
        creep_queen_policy = CreepQueen(
            active=cq_policy.get("active", True),
            max_queens=cq_policy.get("max", 2),
            priority=cq_policy.get("priority", False),
            defend_against_air=cq_policy.get("defend_against_air", True),
            defend_against_ground=cq_policy.get("defend_against_ground", False),
            distance_between_queen_tumors=cq_policy.get(
                "distance_between_queen_tumors", 2
            ),
            distance_between_existing_tumors=cq_policy.get(
                "distance_between_existing_tumors", 7
            ),
            should_tumors_block_expansions=cq_policy.get(
                "distance_between_existing_tumors", False
            ),
            is_active=cq_policy.get(
                "is_active",
                lambda: self.bot.structures(UnitID.CREEPTUMORBURROWED).amount < 20,
            ),
        )
        defence_queen_policy = DefenceQueen(
            active=dq_policy.get("active", True),
            max_queens=dq_policy.get("max", 6),
            priority=dq_policy.get("priority", False),
            defend_against_air=dq_policy.get("defend_against_air", True),
            defend_against_ground=dq_policy.get("defend_against_ground", True),
            rally_point=dq_policy.get(
                "rally_point",
                self.bot.main_base_ramp.bottom_center.towards(
                    self.bot.game_info.map_center, 3
                ),
            ),
        )
        inject_queen_policy = InjectQueen(
            active=iq_policy.get("active", True),
            max_queens=iq_policy.get("max", 6),
            priority=iq_policy.get("priority", True),
            defend_against_air=iq_policy.get("defend_against_air", False),
            defend_against_ground=iq_policy.get("defend_against_ground", False),
        )

        policies = {
            CREEP_POLICY: creep_queen_policy,
            DEFENCE_POLICY: defence_queen_policy,
            INJECT_POLICY: inject_queen_policy,
        }

        return policies
