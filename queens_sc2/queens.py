from typing import Dict, List, Optional
import numpy as np
from sc2 import BotAI
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.position import Point2, Point3
from sc2.unit import Unit
from sc2.units import Units
from queens_sc2.consts import QueenRoles
from queens_sc2.creep import Creep
from queens_sc2.defence import Defence
from queens_sc2.inject import Inject
from queens_sc2.policy import DefenceQueen, CreepQueen, InjectQueen, Policy

CREEP_POLICY: str = "creep_policy"
DEFENCE_POLICY: str = "defence_policy"
INJECT_POLICY: str = "inject_policy"


class Queens:
    def __init__(self, bot: BotAI, debug: bool = False, queen_policy: Dict = None):
        self.bot: BotAI = bot
        self.debug: bool = debug
        self.creep_queen_tags: List[int] = []
        self.defence_queen_tags: List[int] = []
        self.inject_targets: Dict[int, int] = {}
        self.policies: Dict[str, Policy] = self._read_queen_policy(queen_policy)
        self.creep: Creep = Creep(bot, self.policies[CREEP_POLICY])
        self.defence: Defence = Defence(bot, self.policies[DEFENCE_POLICY])
        self.inject: Inject = Inject(bot, self.policies[INJECT_POLICY])
        self.transfuse_dict: Dict[int] = {}
        # key: unit tag, value: when to expire so unit can be transfused again
        self.targets_being_transfused: Dict[int, float] = {}
        self.creep.update_creep_map()

    async def manage_queens(
        self,
        iteration: int,
        air_threats_near_bases: Optional[Units] = None,
        ground_threats_near_bases: Optional[Units] = None,
        queens: Optional[Units] = None,
    ) -> None:
        if self.defence.policy.pass_own_threats:
            air_threats: Units = air_threats_near_bases
            ground_threats: Units = ground_threats_near_bases
        else:
            air_threats: Units = self.defence.enemy_air_threats
            ground_threats: Units = self.defence.enemy_ground_threats

        if queens is None:
            queens: Units = self.bot.units(UnitID.QUEEN)

        if iteration % 8 == 0:
            self.creep.update_creep_map()

        if iteration % 128 == 0:
            Creep.creep_coverage.fget.cache_clear()

        if (
            self.creep.creep_coverage < 50
            or iteration % int(self.creep.creep_coverage / 8) == 0
        ):
            await self.creep.spread_existing_tumors()

        await self._handle_queens(air_threats, ground_threats, queens)

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
                # also assign the dead townhall's queen a new role if she is alive
                queens: Units = self.bot.units(UnitID.QUEEN).tags_in([k])
                if queens:
                    self._assign_queen_role(queens.first)

    def set_new_policy(self, queen_policy, reset_roles: bool = True) -> None:
        self.policies = self._read_queen_policy(queen_policy)
        if reset_roles:
            self.creep_queen_tags = []
            self.defence_queen_tags = []
            self.inject_targets.clear()

        self.creep.update_policy(self.policies[CREEP_POLICY])
        self.defence.update_policy(self.policies[DEFENCE_POLICY])
        self.inject.update_policy(self.policies[INJECT_POLICY])

    def update_attack_target(self, attack_target: Point2) -> None:
        self.defence.set_attack_target(attack_target)

    def update_creep_targets(self, creep_targets: List[Point2]) -> None:
        self.creep.set_creep_targets(creep_targets)

    async def _handle_queens(
        self, air_threats: Units, ground_threats: Units, queens: Units
    ):
        all_close_threats = air_threats.extend(ground_threats)
        creep_priority_enemy_units: Units = self._get_priority_enemy_units(
            all_close_threats, self.creep.policy
        )
        defence_priority_enemy_units: Units = self._get_priority_enemy_units(
            all_close_threats, self.defence.policy
        )
        inject_priority_enemy_units: Units = self._get_priority_enemy_units(
            all_close_threats, self.inject.policy
        )
        print(defence_priority_enemy_units)
        """ Main Queen loop """
        for queen in queens:
            self._assign_queen_role(queen)
            # if any queen has more than 50 energy, she may transfuse
            if queen.energy >= 50:
                # method will return True if queen is transfusing
                if await self._handle_transfuse(queen):
                    continue

            if queen.tag in self.inject_targets.keys():
                await self.inject.handle_unit(
                    air_threats,
                    ground_threats,
                    inject_priority_enemy_units,
                    queen,
                    self.inject_targets[queen.tag],
                )
            elif queen.tag in self.creep_queen_tags:
                await self.creep.handle_unit(
                    air_threats, ground_threats, creep_priority_enemy_units, queen
                )
            elif queen.tag in self.defence_queen_tags:
                await self.defence.handle_unit(
                    air_threats, ground_threats, defence_priority_enemy_units, queen
                )

    async def _handle_transfuse(self, queen: Unit) -> bool:
        """ Deal with a queen transfusing """
        # clear out targets from the dict after a short interval so they may be transfused again
        transfuse_tags = list(self.targets_being_transfused.keys())
        for tag in transfuse_tags:
            if self.targets_being_transfused[tag] > self.bot.time:
                self.targets_being_transfused.pop(tag)

        transfuse_target: Unit = self.defence.get_transfuse_target(
            queen.position, self.targets_being_transfused
        )
        if transfuse_target and transfuse_target is not queen:
            queen(AbilityId.TRANSFUSION_TRANSFUSION, transfuse_target)
            self.targets_being_transfused[transfuse_target.tag] = self.bot.time + 0.4
            return True
        return False

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
        priorities: List[QueenRoles] = []
        ready_townhalls: Units = self.bot.townhalls.ready
        ths_without_queen: Units = ready_townhalls.filter(
            lambda townhall: townhall.tag not in self.inject_targets.values()
        )
        # work out which roles are of priority
        for key, value in self.policies.items():
            if value.active and value.priority:
                max_queens: int = (
                    value.priority if type(value.priority) == int else value.max_queens
                )
                if key == CREEP_POLICY and len(self.creep_queen_tags) < max_queens:
                    priorities.append(QueenRoles.Creep)
                elif (
                    key == DEFENCE_POLICY and len(self.defence_queen_tags) < max_queens
                ):
                    priorities.append(QueenRoles.Defence)
                elif key == INJECT_POLICY and len(self.inject_targets) < min(
                    max_queens, ready_townhalls.amount
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
            # leftover queens get assigned to defence regardless, otherwise queen would do nothing
            else:
                self.defence_queen_tags.append(queen.tag)

    def _queen_has_role(self, queen: Unit) -> bool:
        """
        Checks if we know about queen, if not assign a role
        """
        queen_tag = []
        for tag in [
            self.creep_queen_tags,
            self.defence_queen_tags,
            self.inject_targets.keys(),
        ]:
            if queen.tag in tag:
                queen_tag.append(tag)
        return len(queen_tag) > 0

    def _read_queen_policy(self, queen_policy: Dict) -> Dict[str, Policy]:
        """
        Read the queen policy the user passed in, add default
        params for missing values

        :param queen_policy:
        :type queen_policy: Dict
        :return: new policy with default params for missing values
        :rtype: Dict
        """
        # handle user not passing in a policy
        _queen_policy: Dict = queen_policy if queen_policy else {}
        cq_policy = _queen_policy.get("creep_queens", {})
        dq_policy = _queen_policy.get("defence_queens", {})
        iq_policy = _queen_policy.get("inject_queens", {})

        creep_queen_policy = CreepQueen(
            active=cq_policy.get("active", True),
            max_queens=cq_policy.get("max", 2),
            priority=cq_policy.get("priority", 1),
            defend_against_air=cq_policy.get("defend_against_air", True),
            defend_against_ground=cq_policy.get("defend_against_ground", False),
            distance_between_existing_tumors=cq_policy.get(
                "distance_between_existing_tumors", 10
            ),
            distance_between_queen_tumors=cq_policy.get(
                "distance_between_queen_tumors", 7
            ),
            min_distance_between_existing_tumors=cq_policy.get(
                "min_distance_between_existing_tumors", 7
            ),
            should_tumors_block_expansions=cq_policy.get(
                "should_tumors_block_expansions", False
            ),
            creep_targets=cq_policy.get(
                "creep_targets",
                self._path_expansion_distances(),
            ),
            spread_style=cq_policy.get("spread_style", "targeted"),  # targeted
            rally_point=cq_policy.get(
                "rally_point",
                self.bot.main_base_ramp.bottom_center.towards(
                    self.bot.game_info.map_center, 3
                ),
            ),
            target_perc_coverage=cq_policy.get(
                "target_perc_coverage",
                75.0,
            ),
            first_tumor_position=cq_policy.get(
                "first_tumor_position",
                None,
            ),
            pass_own_threats=cq_policy.get(
                "pass_own_threats",
                False,
            ),
            prioritize_creep=cq_policy.get("prioritize_creep", lambda: False),
            priority_defence_list=cq_policy.get("priority_defence_list", set()),
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
            pass_own_threats=dq_policy.get(
                "pass_own_threats",
                False,
            ),
            priority_defence_list=dq_policy.get("priority_defence_list", set()),
        )

        inject_queen_policy = InjectQueen(
            active=iq_policy.get("active", True),
            max_queens=iq_policy.get("max", 6),
            priority=iq_policy.get("priority", False),
            defend_against_air=iq_policy.get("defend_against_air", False),
            defend_against_ground=iq_policy.get("defend_against_ground", False),
            pass_own_threats=iq_policy.get(
                "pass_own_threats",
                False,
            ),
            priority_defence_list=iq_policy.get("priority_defence_list", set()),
        )

        policies = {
            CREEP_POLICY: creep_queen_policy,
            DEFENCE_POLICY: defence_queen_policy,
            INJECT_POLICY: inject_queen_policy,
        }

        return policies

    def _get_priority_enemy_units(
        self, enemy_threats: Optional[Units], policy: Policy
    ) -> Optional[Units]:
        if enemy_threats and len(policy.priority_defence_list) != 0:
            priority_threats: Units = enemy_threats(policy.priority_defence_list)
            return priority_threats

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

        self.bot.client.debug_text_screen(
            f"Creep Coverage: {str(self.creep.creep_coverage)}%",
            pos=(0.2, 0.66),
            size=13,
            color=(0, 255, 255),
        )

        self.bot.client.debug_text_screen(
            f"Priority defend against: {str(self.defence.policy.priority_defence_list)}",
            pos=(0.2, 0.68),
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

        tumors: Units = self.bot.structures.filter(
            lambda s: s.type_id == UnitID.CREEPTUMORBURROWED
            and s.tag not in self.creep.used_tumors
        )
        if tumors:
            for tumor in tumors:
                self._draw_on_world(tumor.position, f"TUMOR")

    def _draw_on_world(self, pos: Point2, text: str) -> None:
        z_height: float = self.bot.get_terrain_z_height(pos)
        self.bot.client.debug_text_world(
            text,
            Point3((pos.x, pos.y, z_height)),
            color=(0, 255, 255),
            size=12,
        )
