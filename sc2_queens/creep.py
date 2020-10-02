from typing import Dict, List, Optional
import numpy as np

from sc2 import BotAI
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.position import Point2, Pointlike
from sc2.unit import Unit
from sc2.units import Units

from sc2_queens.base_unit import BaseUnit
from sc2_queens.policy import CreepQueen


def _find_random_creep_placement(from_pos: Point2, distance: int) -> Point2:
    from random import randint
    from math import cos, sin

    angle: int = randint(0, 360)
    pos: Point2 = from_pos + (distance * Point2((cos(angle), sin(angle))))

    return pos


class Creep(BaseUnit):
    def __init__(self, bot: BotAI, creep_policy: Dict):
        super().__init__(bot)
        self.policy: CreepQueen = creep_policy
        self.creep_map: np.ndarray = None
        self.creep_targets: List[Point2] = []
        self.creep_target_index: int = 0

    async def handle_unit(self, unit: Unit) -> None:
        self.creep_targets = self.policy.creep_targets
        if self.policy.defend_against_air and self.enemy_air_threats:
            await self.do_queen_micro(unit, self.enemy_air_threats)
        elif self.policy.defend_against_ground and self.enemy_ground_threats:
            await self.do_queen_micro(unit, self.enemy_ground_threats)
        elif unit.energy >= 25 and len(unit.orders) == 0:
            await self.spread_creep(unit)
        elif unit.distance_to(self.policy.rally_point) > 7 and len(unit.orders) == 0:
            unit.move(self.policy.rally_point)

    def update_policy(self, policy) -> None:
        self.policy = policy

    async def spread_creep(self, queen: Unit) -> None:
        if self.creep_target_index >= len(self.creep_targets):
            self.creep_target_index = 0
        self._update_creep_map()
        should_lay_tumor: bool = True
        pos: Point2 = self._find_creep_placement(
            self.creep_targets[self.creep_target_index]
        )
        if (
            (
                not self.policy.should_tumors_block_expansions
                and self._position_blocks_expansion(pos)
            )
            or self.position_near_enemy(pos)
            or self.position_near_enemy_townhall(pos)
        ):
            should_lay_tumor = False
            self.creep_target_index += 1

        if should_lay_tumor:
            queen(AbilityId.BUILD_CREEPTUMOR_QUEEN, pos)
            self.creep_target_index += 1

    async def spread_existing_tumors(self):
        all_tumors: Units = self.bot.structures(
            {UnitID.CREEPTUMOR, UnitID.CREEPTUMORBURROWED}
        )
        tumors: Units = self.bot.structures(UnitID.CREEPTUMORBURROWED).ready
        should_lay_tumor: bool = True
        for tumor in tumors:
            if self.policy.spread_style.upper() == "TARGETED":
                pos: Point2 = self._find_existing_tumor_placement(
                    tumor.position, self.policy.distance_between_existing_tumors
                )
                if pos:
                    tumor(AbilityId.BUILD_CREEPTUMOR_TUMOR, pos)
            else:
                pos: Point2 = _find_random_creep_placement(
                    tumor.position, self.policy.distance_between_existing_tumors
                )
                if (
                    # (
                    #     not self.policy.should_tumors_block_expansions
                    #     and self._position_blocks_expansion(pos)
                    # )
                    self.position_near_enemy(pos)
                    or all_tumors.closer_than(
                        self.policy.distance_between_existing_tumors, pos
                    )
                ):
                    should_lay_tumor = False
                if pos and should_lay_tumor:
                    tumor(AbilityId.BUILD_CREEPTUMOR_TUMOR, pos)

    def _find_creep_placement(self, target: Point2) -> Point2:
        nearest_spot = self.creep_map[
            np.sum(
                np.square(np.abs(self.creep_map - np.array([[target.x, target.y]]))), 1,
            ).argmin()
        ]

        pos = Point2(Pointlike((nearest_spot[0], nearest_spot[1])))
        return pos

    def _find_existing_tumor_placement(
        self, from_pos: Point2, distance: int
    ) -> Optional[Point2]:
        import random

        target: Point2 = random.choice(self.creep_targets)
        possible_placement_area: Point2 = from_pos.towards(target, distance)
        for pos in possible_placement_area.neighbors8:
            if self.bot.is_visible(pos) and self.bot.has_creep(pos):
                return pos

    def _position_blocks_expansion(self, position: Point2) -> bool:
        """ Will the creep tumor block expansion """
        blocks_expansion = False
        for expansion in self.bot.expansion_locations_list:
            if position.distance_to(expansion) < 5:
                blocks_expansion = True
                break
        return blocks_expansion

    def _update_creep_map(self):
        creep = np.where(self.bot.state.creep.data_numpy == 1)
        self.creep_map = np.vstack((creep[1], creep[0])).transpose()