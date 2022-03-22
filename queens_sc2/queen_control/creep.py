import functools
from typing import Dict, List, Optional, Set, Tuple, Union

import numpy as np
from loguru import logger

from sc2.bot_ai import BotAI
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from queens_sc2.kd_trees import KDTrees
from queens_sc2.policy import Policy
from queens_sc2.queen_control.base_unit import BaseUnit

ALL_TUMOR_TYPES: Set[UnitID] = {UnitID.CREEPTUMORBURROWED, UnitID.CREEPTUMORQUEEN, UnitID.CREEPTUMOR}
TARGETED_CREEP_SPREAD: str = "TARGETED"
TIME_TO_CLEAR_PENDING_CREEP_POSITION: int = 10
# 11 seconds before a tumor can be spread again (after it's finished building)
TUMOR_COOLDOWN: int = int(11 * 22.4) + 7


class Creep(BaseUnit):
    creep_map: np.ndarray
    no_creep_map: np.ndarray

    def __init__(
        self,
        bot: BotAI,
        kd_trees: KDTrees,
        creep_policy: Policy,
        map_data: Optional["MapData"],
    ):
        super().__init__(bot, kd_trees, map_data)
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
        self.active_tumors: Dict[int:float] = dict()
        self.tumors_cooldown: Dict[int:int] = dict()
        self.tumor_positions: Set[Point2] = set()

    @property
    @functools.lru_cache()
    def creep_coverage(self) -> float:
        if self.creep_map is not None:
            creep_coverage: int = self.creep_map.shape[0]
            no_creep_coverage: int = self.no_creep_map.shape[0]
            total_tiles: int = creep_coverage + no_creep_coverage
            return 100 * creep_coverage / total_tiles

        return 0.0

    def handle_unit(
        self,
        air_threats_near_bases: Units,
        ground_threats_near_bases: Units,
        priority_enemy_units: Units,
        unit: Unit,
        th_tag: int = 0,
        avoidance_grid: Optional[np.ndarray] = None,
        grid: Optional[np.ndarray] = None,
        nydus_networks: Optional[Units] = None,
        nydus_canals: Optional[Units] = None,
        natural_position: Optional[Point2] = None,
    ) -> None:

        should_spread_creep: bool = self._check_queen_can_spread_creep(unit)
        self.creep_targets = self.policy.creep_targets

        if self.keep_queen_safe(avoidance_grid, grid, unit):
            return
        min_priority: int = 2 if should_spread_creep else 1
        if priority_enemy_units and priority_enemy_units.amount >= min_priority:
            self.do_queen_micro(unit, priority_enemy_units, grid)
        elif self.bot.enemy_units and self.bot.enemy_units.in_attack_range_of(unit):
            self.do_queen_micro(
                unit, self.bot.enemy_units, grid, attack_static_defence=False
            )
        elif (
            self.policy.defend_against_air
            and air_threats_near_bases
            and not should_spread_creep
        ):
            self.do_queen_micro(
                unit, air_threats_near_bases, grid, attack_static_defence=False
            )
        elif (
            self.policy.defend_against_ground
            and ground_threats_near_bases
            and not should_spread_creep
        ):
            self.do_queen_micro(
                unit, ground_threats_near_bases, grid, attack_static_defence=False
            )
        # queen is on route to a tumor but encounters enemy units
        elif (
            unit.is_using_ability(AbilityId.BUILD_CREEPTUMOR)
            and self.bot.enemy_units
            and self.bot.enemy_units.filter(
                lambda enemy: enemy.can_attack_ground
                and enemy.distance_to(unit) < max(unit.air_range, unit.ground_range) + 2
                and enemy.type_id not in {UnitID.OVERLORD}
            )
        ):
            unit.move(self.policy.rally_point)
        elif (
            unit.energy >= 25
            and not unit.is_using_ability(AbilityId.BUILD_CREEPTUMOR)
            and self.creep_coverage < self.policy.target_perc_coverage
        ):
            self.spread_creep(unit, grid)
        elif (
            self.map_data
            and grid is not None
            and not unit.is_using_ability(AbilityId.BUILD_CREEPTUMOR)
            and not self.is_position_safe(grid, unit.position)
        ):
            self.move_towards_safe_spot(unit, grid)
        elif unit.distance_to(
            self.policy.rally_point
        ) > 7 and not unit.is_using_ability(AbilityId.BUILD_CREEPTUMOR):
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

    def set_creep_targets(
        self, creep_targets: Union[List[Point2], List[Tuple[Point2, Point2]]]
    ) -> None:
        self.policy.creep_targets = creep_targets

    def spread_creep(self, queen: Unit, grid: Optional[np.ndarray]) -> None:
        if self.creep_target_index >= len(self.creep_targets):
            self.creep_target_index = 0

        if self.first_tumor and self.policy.first_tumor_position:
            # user has passed in an invalid first tumor position so ignore it
            if not self._valid_creep_placement(self.policy.first_tumor_position):
                self.first_tumor = False
                return
            queen(AbilityId.BUILD_CREEPTUMOR_QUEEN, self.policy.first_tumor_position)
            self._add_tumor_position(self.policy.first_tumor_position)
            # retry a few times, sometimes queen gets blocked when spawning
            if self.first_tumor_retry_attempts > 5:
                self.first_tumor = False
            self.first_tumor_retry_attempts += 1
            return

        # if using map_data, creep will follow ground path to the targets
        if self.map_data:
            pos: Optional[Point2] = self._find_closest_to_target_using_path(
                self.creep_targets[self.creep_target_index], self.creep_map, grid
            )
        else:
            pos: [Point2] = self._find_closest_to_target(
                self.creep_targets[self.creep_target_index], self.creep_map
            )
            # check this position is good, if not try to find something nearby
            if not self._valid_creep_placement(pos):
                new_pos: Optional[Point2] = None
                for p in pos.neighbors8:
                    if self._valid_creep_placement(p):
                        new_pos = p
                        break
                pos = new_pos

        if (
            pos
            and not self.kd_trees.enemy_units_in_range(queen.position, 11).filter(
                lambda u: not u.is_flying
            )
        ):
            queen(AbilityId.BUILD_CREEPTUMOR_QUEEN, pos)
            self._add_tumor_position(pos)
            self.pending_positions.append((pos, self.bot.time))

        # can't lay tumor right now, go back home
        elif queen.distance_to(self.policy.rally_point) > 7:
            queen.move(self.policy.rally_point)

        self.creep_target_index += 1

    def spread_existing_tumors(self) -> None:
        for structure in self.bot.structures:
            tag: int = structure.tag
            if (
                structure.type_id != UnitID.CREEPTUMORBURROWED
                or tag in self.used_tumors
            ):
                continue

            # detect if this tumor is spent
            if not structure.is_idle and isinstance(structure.order_target, Point2):
                self.used_tumors.add(tag)
                continue

            current_frame: int = self.bot.state.game_loop

            # this is a new tumor, add it to our records and continue to next iteration
            if tag not in self.tumors_cooldown:
                self.tumors_cooldown[tag] = current_frame
                continue

            # not ready to spread yet, continue
            if current_frame < self.tumors_cooldown[tag] + TUMOR_COOLDOWN:
                continue

            if tag not in self.active_tumors:
                self.active_tumors[tag] = self.bot.time

            if (
                self.policy.spread_style.upper() == TARGETED_CREEP_SPREAD
                # tumors have 5 seconds to find a targeted spot before resorting to random placement
                and self.active_tumors[tag] > self.bot.time - 5.0
            ):
                pos: Point2 = self._find_existing_tumor_placement(structure.position)
            else:
                pos: Point2 = self._find_random_creep_placement(
                    structure.position, self.policy.distance_between_existing_tumors
                )
            if pos and self._valid_creep_placement(pos):
                self.active_tumors.pop(tag)
                self.tumors_cooldown.pop(tag)
                self._add_tumor_position(pos)
                structure(AbilityId.BUILD_CREEPTUMOR_TUMOR, pos)

    def _clear_pending_positions(self) -> None:
        queen_tumors = self.bot.structures({UnitID.CREEPTUMORQUEEN})

        # recreate the pending position list, depending if a tumor has been placed closeby
        self.pending_positions = [
            pending_position
            for pending_position in self.pending_positions
            if not queen_tumors.closer_than(3, pending_position[0])
            and self.bot.time
            > pending_position[1] + TIME_TO_CLEAR_PENDING_CREEP_POSITION
        ]

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
            if self._valid_creep_placement(new_pos):
                return new_pos

    def _find_random_creep_placement(
        self, from_pos: Point2, distance: int
    ) -> Optional[Point2]:
        random_position: Point2 = self.get_random_position_from(from_pos, distance)
        # go backwards towards tumor till position is found
        for i in range(5):
            if not self.bot.in_map_bounds(random_position):
                return
            creep_pos: Point2 = random_position.towards(from_pos, distance=i)
            if self._valid_creep_placement(creep_pos):
                return creep_pos

    def _find_closest_to_target_using_path(
        self,
        target_pos: Union[Point2, Tuple[Point2, Point2]],
        creep_grid: np.ndarray,
        pathing_grid: np.ndarray,
    ) -> Optional[Point2]:
        # just a list of targets, we path from start location to target
        if isinstance(target_pos, Point2):
            start_point: Point2 = self.bot.start_location
            end_point: Point2 = target_pos
        # list of tuples containing start and end of path, ensure user passed it in correctly
        elif (
            isinstance(target_pos, tuple)
            and len(target_pos) == 2
            and isinstance(target_pos[0], Point2)
            and isinstance(target_pos[1], Point2)
        ):
            start_point: Point2 = target_pos[0]
            end_point: Point2 = target_pos[1]
        # the target_pos makes no sense, provide default values so creep spread still works
        else:
            start_point: Point2 = self.bot.start_location
            end_point: Point2 = self.bot.enemy_start_locations[0]
            logger.warning(
                "queens-sc2 was unable to recognise creep_targets from the policy, using basic creep path"
            )

        path: List[Point2] = self.map_data.pathfind(
            start_point, end_point, pathing_grid, sensitivity=6
        )
        if path:
            # find first point in path that has no creep
            for point in path:
                if not self.bot.has_creep(point):
                    # then get closest creep tile, to this no creep tile
                    new_placement: Point2 = self._find_closest_to_target(point, creep_grid)
                    # check this position is valid
                    if not self._valid_creep_placement(new_placement):
                        for pos in new_placement.neighbors8:
                            if self._valid_creep_placement(pos):
                                return pos
                        # last resort, return the new_placement anyway
                        return new_placement
                    else:
                        return new_placement

    def position_near_nydus_worm(self, position: Point2) -> bool:
        """Will the creep tumor block expansion"""
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
        """Using the policy option, check if other tumors are too close"""
        min_distance: int = self.policy.distance_between_queen_tumors
        # passing 0 or False value into the policy will turn this check off and save computation
        if not min_distance:
            return False
        tumors: Units = self.bot.structures.filter(
            lambda s: s.type_id in ALL_TUMOR_TYPES
        )
        for tumor in tumors:
            if position.distance_to(tumor) < min_distance:
                return True

        # check in the pending creep locations (queen on route to lay tumor)
        for pending_position in self.pending_positions:
            if position.distance_to(pending_position[0]) < min_distance:
                return True

        return False

    def _add_tumor_position(self, position: Point2) -> None:
        def round_position(pos: float, base=0.5) -> float:
            return base * round(pos / base)
        x: float = round_position(position.x)
        if int(x * 10) % 10 == 0:
            x += 0.5
        y: float = round_position(position.y)
        if int(y * 10) % 10 == 0:
            y += 0.5
        pos: Point2 = Point2((x, y))
        self.tumor_positions.add(pos)

    def _valid_creep_placement(self, position: Point2) -> bool:
        placeable: bool = self.bot.game_info.placement_grid[position.rounded] == 1
        return (
            placeable
            and self.bot.is_visible(position)
            and self.bot.has_creep(position)
            and position not in self.tumor_positions
            and position not in self.pending_positions
            and (
                self.policy.should_tumors_block_expansions is False
                and not self.position_blocks_expansion(position)
            )
            and not self.position_near_enemy_townhall(position)
            and not self.position_near_nydus_worm(position)
            and not self._existing_tumors_too_close(position)
            and not self.position_near_enemy(position)
        )
