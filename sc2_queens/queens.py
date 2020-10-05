from typing import Dict, List, Optional
import numpy as np

from sc2 import BotAI
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.position import Point2, Point3
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
    def __init__(self, bot: BotAI, debug: bool = False, **queen_policy: Dict):
        self.bot: BotAI = bot
        self.debug: bool = debug
        self.creep_queen_tags: List[int] = []
        self.defence_queen_tags: List[int] = []
        self.inject_targets: Dict[int, int] = {}
        self.policies: Dict[str, Policy] = self._read_queen_policy(**queen_policy)
        self.creep: Creep = Creep(bot, self.policies[CREEP_POLICY])
        self.defence: Defence = Defence(bot, self.policies[DEFENCE_POLICY])
        self.inject: Inject = Inject(bot, self.policies[INJECT_POLICY])

    async def manage_queens(
        self, iteration: int, queens: Optional[Units] = None
    ) -> None:
        if queens is None:
            queens: Units = self.bot.units(UnitID.QUEEN)

        if iteration % 16 == 0:
            await self.creep.spread_existing_tumors()

        for queen in queens:
            self._assign_queen_role(queen)
            if queen.tag in self.inject_targets.keys():
                await self.inject.handle_unit(queen, self.inject_targets[queen.tag])
            elif queen.tag in self.creep_queen_tags:
                await self.creep.handle_unit(queen)
            elif queen.tag in self.defence_queen_tags:
                await self.defence.handle_unit(queen)
        if self.debug:
            await self._draw_debug_info()

    def remove_unit(self, unit_tag) -> None:
        self.creep_queen_tags = [
            tag for tag in self.creep_queen_tags if tag != unit_tag
        ]
        self.defence_queen_tags = [
            tag for tag in self.defence_queen_tags if tag != unit_tag
        ]
        try:
            del self.inject_targets[unit_tag]
        except KeyError:
            pass
        # here we check if townhall was destroyed
        for k in self.inject_targets.copy():
            if self.inject_targets[k] == unit_tag:
                del self.inject_targets[k]
                # also assign the dead townhall's queen a new role
                queens: Units = self.bot.units(UnitID.QUEEN).tags_in([k])
                if queens:
                    self._assign_queen_role(queens.first)

    def set_new_policy(self, reset_roles: bool = True, **queen_policy) -> None:
        self.policies = self._read_queen_policy(**queen_policy)
        if reset_roles:
            self.creep_queen_tags = []
            self.defence_queen_tags = []
            self.inject_targets.clear()

        self.creep.update_policy(self.policies[CREEP_POLICY])
        self.defence.update_policy(self.policies[DEFENCE_POLICY])
        self.inject.update_policy(self.policies[INJECT_POLICY])

    def update_attack_target(self, attack_target: Point2) -> None:
        self.defence.policy.attack_target = attack_target

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
        # if there are priority clashes, revert to:
        # inject, creep, defence
        # if there is a priority, assign it to the relevant group
        priorities: List[str] = []
        ready_townhalls: Units = self.bot.townhalls.ready
        ths_without_queen: Units = ready_townhalls.filter(
            lambda townhall: townhall.tag not in self.inject_targets.values()
        )
        # work out which roles are of priority
        for key, value in self.policies.items():
            if value.active and value.priority:
                if (
                    key == CREEP_POLICY
                    and len(self.creep_queen_tags) < value.max_queens
                ):
                    priorities.append(QueenRoles.Creep)
                elif (
                    key == DEFENCE_POLICY
                    and len(self.defence_queen_tags) < value.max_queens
                ):
                    priorities.append(QueenRoles.Defence)
                elif key == INJECT_POLICY and len(self.inject_targets) < min(
                    value.max_queens, ready_townhalls.amount
                ):
                    priorities.append(QueenRoles.Inject)
        if QueenRoles.Inject in priorities and ths_without_queen:
            # pick th closest to queen, so she doesn't have to walk too far
            th: Unit = ths_without_queen.closest_to(queen)
            if th.tag not in self.inject_targets.values():
                self.inject_targets[queen.tag] = th.tag
        elif QueenRoles.Creep in priorities:
            self.creep_queen_tags.append(queen.tag)
        elif QueenRoles.Defence in priorities:
            self.defence_queen_tags.append(queen.tag)
        # if we get to here, then assign to inject, then creep then defence
        else:
            if (
                len(self.inject_targets)
                < min(self.policies[INJECT_POLICY].max_queens, ready_townhalls.amount)
                and self.policies[INJECT_POLICY].active
            ):
                if ths_without_queen:
                    # pick th closest to queen
                    th: Unit = ths_without_queen.closest_to(queen)
                    self.inject_targets[queen.tag] = th.tag
            elif (
                len(self.creep_queen_tags) < self.policies[CREEP_POLICY].max_queens
                and self.policies[CREEP_POLICY].active
            ):
                self.creep_queen_tags.append(queen.tag)
            # leftover queens get assigned to defence regardless
            else:
                self.defence_queen_tags.append(queen.tag)

    def _queen_has_role(self, queen: Unit) -> bool:
        """
        Checks if we know about queen, if not assign a role
        """
        queen_tag: List[int] = [
            tag
            for tag in [
                self.creep_queen_tags,
                self.defence_queen_tags,
                self.inject_targets.keys(),
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
                "distance_between_existing_tumors", 10
            ),
            should_tumors_block_expansions=cq_policy.get(
                "should_tumors_block_expansions", False
            ),
            creep_targets=cq_policy.get(
                "creep_targets", self._path_expansion_distances(),
            ),
            spread_style=cq_policy.get("spread_style", "targeted"),  # targeted
            rally_point=cq_policy.get(
                "rally_point",
                self.bot.main_base_ramp.bottom_center.towards(
                    self.bot.game_info.map_center, 3
                ),
            ),
        )
        defence_queen_policy = DefenceQueen(
            active=dq_policy.get("active", True),
            max_queens=dq_policy.get("max", 6),
            priority=dq_policy.get("priority", False),
            defend_against_air=dq_policy.get("defend_against_air", True),
            defend_against_ground=dq_policy.get("defend_against_ground", True),
            attack_condition=dq_policy.get("attack_condition", lambda: False),
            attack_target=dq_policy.get(
                "attack_target", self.bot.enemy_start_locations[0]
            ),
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

    def _path_expansion_distances(self) -> List[Point2]:
        """
        If user passes no creep targets in policy, we use expansion locations
        """
        expansion_distances = []
        spawn_loc = self.bot.start_location
        for el in self.bot.expansion_locations_list:
            if (
                Point2(spawn_loc).position.distance_to(el)
                < self.bot.EXPANSION_GAP_THRESHOLD
            ):
                continue

            expansion_distances.append(el)
        return expansion_distances

    async def _draw_debug_info(self) -> None:
        self.bot.client.debug_text_screen(
            f"Creep Queens Amount: {str(len(self.creep_queen_tags))}, "
            f"Policy Amount: {str(self.policies[CREEP_POLICY].max_queens)}",
            pos=(0.2, 0.6),
            size=13,
            color=(0, 255, 255),
        )
        self.bot.client.debug_text_screen(
            f"Defence Queens Amount: {str(len(self.defence_queen_tags))}, "
            f"Policy Amount (this can go over): {str(self.policies[DEFENCE_POLICY].max_queens)}",
            pos=(0.2, 0.62),
            size=13,
            color=(0, 255, 255),
        )
        self.bot.client.debug_text_screen(
            f"Inject Queens Amount: {str(len(self.inject_targets.keys()))}, "
            f"Policy Amount: {str(self.policies[INJECT_POLICY].max_queens)}",
            pos=(0.2, 0.64),
            size=13,
            color=(0, 255, 255),
        )

        queens: Units = self.bot.units(UnitID.QUEEN)
        if queens:
            for queen in queens:
                # don't use elif, to check for bugs (queen more than one role)
                if queen.tag in self.creep_queen_tags:
                    self._draw_on_world(queen.position, f"CREEP {queen.tag}")
                if queen.tag in self.defence_queen_tags:
                    self._draw_on_world(queen.position, f"DEFENCE {queen.tag}")
                if queen.tag in self.inject_targets.keys():
                    self._draw_on_world(queen.position, f"INJECT {queen.tag}")

    def _draw_on_world(self, pos: Point2, text: str) -> None:
        z_height: float = self.bot.get_terrain_z_height(pos)
        self.bot.client.debug_text_world(
            text, Point3((pos.x, pos.y, z_height)), color=(0, 255, 255), size=12,
        )
