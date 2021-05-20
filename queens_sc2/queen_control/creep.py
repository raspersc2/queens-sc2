import functools
from typing import List, Optional, Set, Tuple

import numpy as np
from sc2 import BotAI
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.position import Point2, Pointlike
from sc2.unit import Unit
from sc2.units import Units

from queens_sc2.queen_control.base_unit import BaseUnit
from queens_sc2.policy import Policy

TARGETED_CREEP_SPREAD: str = "TARGETED"
TIME_TO_CLEAR_PENDING_CREEP_POSITION: int = 20


class Creep(BaseUnit):
    creep_map: np.ndarray
    no_creep_map: np.ndarray

    def __init__(self, bot: BotAI, creep_policy: Policy, map_data: Optional["MapData"]):
        super().__init__(bot, map_data)
        self.policy = creep_policy
        self.creep_targets: List[Point2] = []
        self.creep_target_index: int = 0
        pathable: np.ndarray = np.where(self.bot.game_info.pathing_grid.data_numpy == 1)
        self.pathing_tiles: np.ndarray = np.vstack(
            (pathable[1], pathable[0])
        ).transpose()
        self.used_tumors: Set[int] = set()
        self.first_tumor: bool = True
        self.first_tumor_retry_attempts: int = 0
        # keep track of positions where queen is on route to lay a tumor
        # tuple where first element is position, and second the time it was added so we can clear it out if need be
        self.pending_positions: List[Tuple[Point2, float]] = []

    @property
    @functools.lru_cache()
    def creep_coverage(self) -> float:
        if self.creep_map is not None:
            creep_coverage: int = self.creep_map.shape[0]
            no_creep_coverage: int = self.no_creep_map.shape[0]
            total_tiles: int = creep_coverage + no_creep_coverage
            return 100 * creep_coverage / total_tiles

        return 0.0

    async def handle_unit(
        self,
        air_threats_near_bases: Units,
        ground_threats_near_bases: Units,
        priority_enemy_units: Units,
        unit: Unit,
        th_tag: int = 0,
        grid: Optional[np.ndarray] = None,
        nydus_networks: Optional[Units] = None,
        nydus_canals: Optional[Units] = None,
    ) -> None:

        should_spread_creep: bool = self._check_queen_can_spread_creep(unit)
        self.creep_targets = self.policy.creep_targets

        if priority_enemy_units:
            await self.do_queen_micro(unit, priority_enemy_units)
        elif (
            self.policy.defend_against_air
            and air_threats_near_bases
            and not should_spread_creep
        ):
            await self.do_queen_micro(unit, air_threats_near_bases)
        elif (
            self.policy.defend_against_ground
            and ground_threats_near_bases
            and not should_spread_creep
        ):
            await self.do_queen_micro(unit, ground_threats_near_bases)
        elif self.bot.enemy_units and self.bot.enemy_units.filter(
            # custom filter to replace in_attack_range_of so that it can be used with memory units
            lambda enemy: enemy.position.distance_to(unit)
            < max(unit.air_range, unit.ground_range)
        ):
            unit.move(self.policy.rally_point)
        elif (
            unit.energy >= 25
            and len(unit.orders) == 0
            and self.creep_coverage < self.policy.target_perc_coverage
        ):
            await self.spread_creep(unit, grid)
        elif unit.distance_to(self.policy.rally_point) > 7:
            if len(unit.orders) > 0:
                if unit.orders[0].ability.button_name != "CreepTumor":
                    unit.move(self.policy.rally_point)
            elif len(unit.orders) == 0:
                unit.move(self.policy.rally_point)
        # check if tumor has been placed at a location yet
        self._clear_pending_positions()

    def update_policy(self, policy: Policy) -> None:
        self.policy = policy

    def _check_queen_can_spread_creep(self, queen: Unit) -> bool:
        return queen.energy >= 25 and self.policy.prioritize_creep()

    def set_creep_targets(self, creep_targets: List[Point2]) -> None:
        self.policy.creep_targets = creep_targets

    async def spread_creep(self, queen: Unit, grid: Optional[np.ndarray]) -> None:
        if self.creep_target_index >= len(self.creep_targets):
            self.creep_target_index = 0

        if self.first_tumor and self.policy.first_tumor_position:
            queen(AbilityId.BUILD_CREEPTUMOR_QUEEN, self.policy.first_tumor_position)
            # retry a few times, sometimes queen gets blocked when spawning
            if self.first_tumor_retry_attempts > 5:
                self.first_tumor = False
            self.first_tumor_retry_attempts += 1
            return

        should_lay_tumor: bool = True
        # if using map_data, creep will follow ground path to the targets
        if self.map_data:
            if grid is None:
                grid = self.map_data.get_pyastar_grid()
            pos: Point2 = self._find_closest_to_target_using_path(
                self.creep_targets[self.creep_target_index], self.creep_map, grid
            )

        else:
            pos: Point2 = self._find_closest_to_target(
                self.creep_targets[self.creep_target_index], self.creep_map
            )

        if (
            not pos
            or (
                self.policy.should_tumors_block_expansions is False
                and self.position_blocks_expansion(pos)
            )
            or self.position_near_enemy(pos)
            or self.position_near_enemy_townhall(pos)
            or self.position_near_nydus_worm(pos)
            or self._existing_tumors_too_close(pos)
        ):
            should_lay_tumor = False
            self.creep_target_index += 1

        if should_lay_tumor:
            queen(AbilityId.BUILD_CREEPTUMOR_QUEEN, pos)
            self.pending_positions.append((pos, self.bot.time))
            self.creep_target_index += 1
        # can't lay tumor right now, go back home
        elif queen.distance_to(self.policy.rally_point) > 7:
            queen.move(self.policy.rally_point)

    async def spread_existing_tumors(self):
        tumors: Units = self.bot.structures.filter(
            lambda s: s.type_id == UnitID.CREEPTUMORBURROWED
            and s.tag not in self.used_tumors
        )
        if tumors:
            all_tumors_abilities = await self.bot.get_available_abilities(tumors)
            for i, abilities in enumerate(all_tumors_abilities):
                tumor = tumors[i]
                if not tumor.is_idle and isinstance(tumor.order_target, Point2):
                    self.used_tumors.add(tumor.tag)
                    continue

                if AbilityId.BUILD_CREEPTUMOR_TUMOR in abilities:
                    should_lay_tumor: bool = True
                    if self.policy.spread_style.upper() == TARGETED_CREEP_SPREAD:
                        pos: Point2 = self._find_existing_tumor_placement(
                            tumor.position
                        )
                    else:
                        pos: Point2 = self._find_random_creep_placement(
                            tumor.position, self.policy.distance_between_existing_tumors
                        )
                    if pos:
                        if (
                            not self.policy.should_tumors_block_expansions
                            and self.position_blocks_expansion(pos)
                        ) or self.position_near_enemy(pos):
                            should_lay_tumor = False
                        if should_lay_tumor:
                            tumor(AbilityId.BUILD_CREEPTUMOR_TUMOR, pos)

    def _clear_pending_positions(self) -> None:
        queen_tumors = self.bot.structures({UnitID.CREEPTUMORQUEEN})
        if not queen_tumors:
            return

        # recreate the pending position list, depending if a tumor has been placed closeby
        self.pending_positions = [
            pending_position
            for pending_position in self.pending_positions
            if not queen_tumors.closer_than(3, pending_position[0])
            and self.bot.time - TIME_TO_CLEAR_PENDING_CREEP_POSITION
            < pending_position[1]
        ]

    def _find_creep_placement(self, target: Point2) -> Point2:
        nearest_spot = self.creep_map[
            np.sum(
                np.square(np.abs(self.creep_map - np.array([[target.x, target.y]]))),
                1,
            ).argmin()
        ]

        pos = Point2(Pointlike((nearest_spot[0], nearest_spot[1])))
        return pos

    def _find_existing_tumor_placement(self, from_pos: Point2) -> Optional[Point2]:

        # find closest no creep tile that is in pathing grid
        target: Point2 = self._find_closest_to_target(from_pos, self.no_creep_map)

        # start at possible placement area, and move back till we find a spot
        for i, x in enumerate(
            range(
                self.policy.min_distance_between_existing_tumors,
                self.policy.distance_between_existing_tumors,
            )
        ):
            new_pos: Point2 = from_pos.towards(
                target, self.policy.distance_between_existing_tumors - i
            )
            if (
                self.bot.is_visible(new_pos)
                and self.bot.has_creep(new_pos)
                and self.bot.in_pathing_grid(new_pos)
            ):
                return new_pos

    def _find_random_creep_placement(
        self, from_pos: Point2, distance: int
    ) -> Optional[Point2]:
        from random import randint
        from math import cos, sin

        angle: int = randint(0, 360)
        pos: Point2 = from_pos + (distance * Point2((cos(angle), sin(angle))))
        # go backwards towards tumor till position is found
        for i in range(5):
            creep_pos: Point2 = pos.towards(from_pos, distance=i)
            # check the position is within the map
            if (
                creep_pos.x < 0
                or creep_pos.x > self.bot.game_info.map_size[0]
                or creep_pos.y < 0
                or creep_pos.y >= self.bot.game_info.map_size[1]
            ):
                continue
            if self.bot.in_pathing_grid(creep_pos) and self.bot.has_creep(creep_pos):
                return creep_pos

    def _find_closest_to_target_using_path(
        self, target_pos: Point2, creep_grid: np.ndarray, pathing_grid: np.ndarray
    ) -> Optional[Point2]:
        path: List[Point2] = self.map_data.pathfind(
            self.bot.start_location, target_pos, pathing_grid
        )
        if path:
            # find first point in path that has no creep
            for point in path:
                if not self.bot.has_creep(point):
                    # then get closest creep tile, to this no creep tile
                    return self._find_closest_to_target(point, creep_grid)

    def position_blocks_expansion(self, position: Point2) -> bool:
        """ Will the creep tumor block expansion """
        blocks_expansion: bool = False
        for expansion in self.bot.expansion_locations_list:
            if position.distance_to(expansion) < 6:
                blocks_expansion = True
                break
        return blocks_expansion

    def position_near_nydus_worm(self, position: Point2) -> bool:
        """ Will the creep tumor block expansion """
        is_too_close: bool = False
        worms: Units = self.bot.structures(UnitID.NYDUSCANAL)
        for worm in worms:
            # worms spread creep at a 10.5 radius, add a bit of leeway
            if position.distance_to(worm) < 12:
                is_too_close = True
                break
        return is_too_close

    def update_creep_map(self) -> None:
        creep: np.ndarray = np.where(self.bot.state.creep.data_numpy == 1)
        self.creep_map = np.vstack((creep[1], creep[0])).transpose()
        no_creep: np.ndarray = np.where(
            (self.bot.state.creep.data_numpy == 0)
            & (self.bot.game_info.pathing_grid.data_numpy == 1)
        )
        self.no_creep_map = np.vstack((no_creep[1], no_creep[0])).transpose()

    def _existing_tumors_too_close(self, position: Point2) -> bool:
        """ Using the policy option, check if other tumors are too close """
        min_distance: int = self.policy.distance_between_queen_tumors
        # passing 0 or False value into the policy will turn this check off and save computation
        if not min_distance:
            return False
        tumors: Units = self.bot.structures.filter(
            lambda s: s.type_id in {UnitID.CREEPTUMORBURROWED, UnitID.CREEPTUMORQUEEN}
        )
        for tumor in tumors:
            if position.distance_to(tumor) < min_distance:
                return True

        # check in the pending creep locations (queen on route to lay tumor)
        for pending_position in self.pending_positions:
            if position.distance_to(pending_position[0]) < min_distance:
                return True

        return False
