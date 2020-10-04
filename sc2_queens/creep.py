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


class Creep(BaseUnit):
    def __init__(self, bot: BotAI, creep_policy: Dict):
        super().__init__(bot)
        self.policy: CreepQueen = creep_policy
        self.creep_map: np.ndarray = None
        self.no_creep_map: np.ndarray = None
        self.creep_targets: List[Point2] = []
        self.creep_target_index: int = 0
        pathable: np.ndarray = np.where(self.bot.game_info.pathing_grid.data_numpy == 1)
        self.pathing_tiles: np.ndarray = np.vstack(
            (pathable[1], pathable[0])
        ).transpose()

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
        pos: Point2 = self._find_closest_to_target(
            self.creep_targets[self.creep_target_index], self.creep_map
        )

        if (
            (
                self.policy.should_tumors_block_expansions is False
                and self.position_blocks_expansion(pos)
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
        tumors: Units = self.bot.structures(UnitID.CREEPTUMORBURROWED).ready

        for tumor in tumors:
            should_lay_tumor: bool = True
            if self.policy.spread_style.upper() == "TARGETED":
                pos: Point2 = await self._find_existing_tumor_placement(tumor.position)
            else:
                pos: Point2 = await self._find_random_creep_placement(tumor.position)
            if pos:
                if (
                    not self.policy.should_tumors_block_expansions
                    and self.position_blocks_expansion(pos)
                ) or self.position_near_enemy(pos):
                    should_lay_tumor = False
                if should_lay_tumor:
                    tumor(AbilityId.BUILD_CREEPTUMOR_TUMOR, pos)

    def _find_creep_placement(self, target: Point2) -> Point2:
        nearest_spot = self.creep_map[
            np.sum(
                np.square(np.abs(self.creep_map - np.array([[target.x, target.y]]))), 1,
            ).argmin()
        ]

        pos = Point2(Pointlike((nearest_spot[0], nearest_spot[1])))
        return pos

    async def _find_existing_tumor_placement(
        self, from_pos: Point2
    ) -> Optional[Point2]:

        # find closest no creep tile that is in pathing grid
        target: Point2 = self._find_closest_to_target(from_pos, self.no_creep_map)

        # start at possible placement area, and move back till we find a spot
        for i in range(self.policy.distance_between_existing_tumors):
            new_pos: Point2 = from_pos.towards(
                target, self.policy.distance_between_existing_tumors - i
            )
            if (
                self.bot.is_visible(new_pos)
                and self.bot.has_creep(new_pos)
                and self.bot.in_pathing_grid(new_pos)
            ):
                return new_pos

    async def _find_random_creep_placement(
        self, from_pos: Point2, distance: int
    ) -> Optional[Point2]:
        from random import randint
        from math import cos, sin

        angle: int = randint(0, 360)
        pos: Point2 = from_pos + (distance * Point2((cos(angle), sin(angle))))
        # go backwards towards tumor till position is found
        for i in range(5):
            creep_pos: Point2 = pos.towards(from_pos, distance=i)
            if self.bot.has_creep(creep_pos):
                return creep_pos

    def _find_closest_to_target(self, from_pos: Point2, grid: np.ndarray) -> Point2:
        nearest_spot = grid[
            np.sum(
                np.square(np.abs(grid - np.array([[from_pos.x, from_pos.y]]))), 1,
            ).argmin()
        ]

        pos = Point2(Pointlike((nearest_spot[0], nearest_spot[1])))
        return pos

    def position_blocks_expansion(self, position: Point2) -> bool:
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
        no_creep = np.where(
            (self.bot.state.creep.data_numpy == 0)
            & (self.bot.game_info.pathing_grid.data_numpy == 1)
        )
        self.no_creep_map = np.vstack((no_creep[1], no_creep[0])).transpose()
