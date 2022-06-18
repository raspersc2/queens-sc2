import math
from abc import ABC, abstractmethod
from math import cos, sin
from random import randint
from typing import Dict, List, Optional, Set

import numpy as np
from scipy import spatial

from queens_sc2.cache import property_cache_once_per_frame
from queens_sc2.consts import (
    CHANGELING_TYPES,
    GROUND_TOWNHALL_TYPES,
    QUEEN_TURN_RATE,
    UNITS_TO_TRANSFUSE,
)
from queens_sc2.kd_trees import KDTrees
from queens_sc2.policy import Policy
from sc2.bot_ai import BotAI
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.position import Point2, Pointlike
from sc2.unit import Unit
from sc2.units import Units

EXCLUDE_AIR_THREATS: Set[UnitID] = {UnitID.OVERLORD, UnitID.OVERSEER, UnitID.OBSERVER}
EXCLUDE_FROM_ATTACK_TARGETS: Set[UnitID] = {UnitID.MULE, UnitID.EGG, UnitID.LARVA}
EXCLUDE_FROM_POS_NEAR_ENEMY: Set[UnitID] = {
    UnitID.DRONE,
    UnitID.SCV,
    UnitID.PROBE,
    UnitID.CHANGELING,
    UnitID.CHANGELINGMARINE,
    UnitID.CHANGELINGZERGLING,
    UnitID.CHANGELINGZERGLINGWINGS,
    UnitID.CHANGELINGZEALOT,
    UnitID.CHANGELINGMARINESHIELD,
    UnitID.OVERLORD,
    UnitID.OVERSEER,
    UnitID.OBSERVER,
}
STATIC_DEFENCE: Set[UnitID] = {
    UnitID.BUNKER,
    UnitID.PHOTONCANNON,
    UnitID.PLANETARYFORTRESS,
    UnitID.SHIELDBATTERY,
    UnitID.SPINECRAWLER,
}


class BaseUnit(ABC):
    policy: Policy

    def __init__(self, bot: BotAI, kd_trees: KDTrees, map_data: "MapData"):
        self.bot: BotAI = bot
        self.kd_trees: KDTrees = kd_trees
        self.map_data: Optional["MapData"] = map_data

    @property_cache_once_per_frame
    def enemy_air_threats(self) -> Units:
        air_threats: Units = Units([], self.bot)
        air_units: Units = self.bot.enemy_units.flying
        threats: Units = Units([], self.bot)
        if air_units:
            for th in self.bot.townhalls.ready:
                closest_enemy: Unit = air_units.closest_to(th)
                if closest_enemy.position.distance_to(th) < 18.0:
                    air_threats.extend(
                        self.bot.enemy_units.filter(
                            lambda unit: unit.is_flying
                            and not unit.is_hallucination
                            and unit.type_id not in EXCLUDE_AIR_THREATS
                        )
                    )
            threats = air_threats
        return threats

    @property_cache_once_per_frame
    def enemy_ground_threats(self) -> Units:
        ground_threats: Units = Units([], self.bot)
        ground_units: Units = self.bot.all_enemy_units.not_flying
        threats: Units = Units([], self.bot)
        if ground_units:
            for th in self.bot.townhalls:
                closest_enemy: Unit = ground_units.closest_to(th)
                if closest_enemy.position.distance_to(th) < 18:
                    ground_threats.extend(
                        ground_units.filter(
                            lambda unit: not unit.is_hallucination
                            and not unit.is_burrowed
                            and unit.type_id not in CHANGELING_TYPES
                        )
                    )
            threats = ground_threats
        return threats

    @abstractmethod
    def handle_unit(
        self,
        air_threats_near_bases: Units,
        ground_threats_near_bases: Units,
        priority_enemy_units: Units,
        unit: Unit,
        in_range_of_rally_tags: Set[int],
        queens: Units,
        th_tag: int = 0,
        avoidance_grid: Optional[np.ndarray] = None,
        grid: Optional[np.ndarray] = None,
        nydus_networks: Optional[Units] = None,
        nydus_canals: Optional[Units] = None,
        natural_position: Optional[Point2] = None,
    ) -> None:
        pass

    @abstractmethod
    def update_policy(self, policy: Policy) -> None:
        pass

    # noinspection PyMethodMayBeStatic
    def angle_to(self, from_pos: Point2, to_pos: Point2) -> float:
        """Angle from point to other point in radians"""
        return math.atan2(to_pos.y - from_pos.y, to_pos.x - to_pos.x)

    # noinspection PyMethodMayBeStatic
    def angle_diff(self, a, b) -> float:
        """Absolute angle difference between 2 angles"""
        if a < 0:
            a += math.pi * 2
        if b < 0:
            b += math.pi * 2
        return math.fabs(a - b)

    def attack_ready(self, unit: Unit, target: Unit) -> bool:
        """
        Determine whether the unit can attack the target by the time the unit faces the target.
        Thanks Sasha for her example code.
        """
        # takes around 4-5 frames for both attacks (14.206 frames from attack start till next attack is ready)
        # better to get both attacks off then kite a little bit later
        if unit.weapon_cooldown > 9:
            return True
        # Time elapsed per game step
        step_time = self.bot.client.game_step / 22.4

        # Time it will take for unit to turn to face target
        angle = self.angle_diff(
            unit.facing, self.angle_to(unit.position, target.position)
        )
        turn_time = angle / self.get_turn_speed()

        # Time it will take for unit to move in range of target
        distance = (
            unit.position.distance_to(target)
            - unit.radius
            - target.radius
            - self.range_vs_target(unit, target)
        )
        distance = max(0, distance)
        move_time = distance / (unit.real_speed * 1.4)

        return step_time + turn_time + move_time >= unit.weapon_cooldown / 22.4

    def keep_queen_safe(
        self,
        avoidance_grid: Optional[np.ndarray],
        grid: Optional[np.ndarray],
        queen: Unit,
    ) -> bool:
        if queen.has_buff(BuffId.LOCKON):
            if self.map_data:
                path: List[Point2] = self.map_data.pathfind(
                    queen.position, self.bot.start_location, grid, sensitivity=2
                )
                if not path or len(path) == 0:
                    move_to: Point2 = self.bot.start_location
                else:
                    move_to: Point2 = path[0]
                queen.move(move_to)
                return True
            else:
                # use MapAnalyzer if you want better lock on avoidance :)
                queen.move(self.bot.start_location)
                return True
        if self.map_data and not self.is_position_safe(avoidance_grid, queen.position):
            self.move_towards_safe_spot(queen, grid)
            return True
        return False

    def do_queen_micro(
        self,
        queen: Unit,
        enemy: Units,
        grid: Optional[np.ndarray] = None,
        attack_static_defence: bool = True,
    ) -> None:
        if not queen:
            return
        if attack_static_defence:
            excluded_enemy: Set[UnitID] = EXCLUDE_FROM_ATTACK_TARGETS
        else:
            excluded_enemy: Set[UnitID] = EXCLUDE_FROM_ATTACK_TARGETS.union(
                STATIC_DEFENCE
            )
        _enemy: Units = enemy.filter(
            lambda u: u.type_id not in excluded_enemy
            and (not u.is_cloaked or u.is_cloaked and u.is_revealed)
            and (not u.is_burrowed or u.is_burrowed and u.is_visible)
        )
        in_range_enemies: Units = self.kd_trees.get_enemies_in_attack_range_of(queen)
        if in_range_enemies:
            target: Unit = self.get_target_from_in_range_enemies(in_range_enemies)
            if target:
                if self.attack_ready(queen, target):
                    queen.attack(target)
                elif self.map_data and grid is not None:
                    self.move_towards_safe_spot(queen, grid)
                else:
                    distance: float = queen.ground_range + queen.radius + target.radius
                    move_to: Point2 = target.position.towards(queen, distance)
                    if self.bot.in_pathing_grid(move_to):
                        queen.move(move_to)
            else:
                queen.attack(in_range_enemies.center)
        elif _enemy:
            queen.move(_enemy.closest_to(queen).position)
        else:
            # if we get here, it's because we can't see the enemy, try to move to the nearest spore if possible
            if enemy and self.map_data and grid is not None:
                # have overseer nearby, attack-move to enemy till above logic picks up the fight
                if overseers := self.bot.units(UnitID.OVERSEER):
                    if overseers.closest_to(queen).distance_to(queen) < 10.0:
                        queen.attack(enemy.center)
                        return
                if spores := self.bot.structures(UnitID.SPORECRAWLER):
                    spore: Unit = spores.closest_to(queen)
                    path: List[Point2] = self.map_data.pathfind(
                        queen.position, spore.position, grid, sensitivity=2
                    )
                    if path:
                        queen.move(path[0])
                    else:
                        queen.move(spore.position)
                else:
                    self.move_towards_safe_spot(queen, grid)
            elif enemy:
                closest_enemy: Unit = enemy.closest_to(queen)
                # not attacking right now so move back out of range of enemy
                distance: float = (
                    queen.ground_range + queen.radius + closest_enemy.radius + 1.0
                )
                move_to: Point2 = closest_enemy.position.towards(queen, distance)
                if self.bot.in_pathing_grid(move_to):
                    queen.move(move_to)

    def do_queen_offensive_micro(
        self, queen: Unit, offensive_pos: Point2, queens: Units
    ) -> None:
        if not queen:
            return
        attack_target: Point2 = (
            offensive_pos if offensive_pos else self.bot.enemy_start_locations[0]
        )
        own_close_queens: Units = self.kd_trees.own_units_in_range_of_point(
            queen.position, 5
        ).filter(lambda u: u.type_id == UnitID.QUEEN)
        if in_attack_range := self.kd_trees.get_enemies_in_attack_range_of(queen):
            target: Unit = self.get_target_from_in_range_enemies(in_attack_range)
            if self.attack_ready(queen, target):
                queen.attack(target)
            else:
                # loose queen_control should try to rejoin the queen pack
                if own_close_queens.amount <= 3:
                    queen.move(queens.center)
                # otherwise move forward between attacks, since Queen is slow and can get stuck behind each other
                else:
                    queen.move(attack_target)
        else:
            queen.attack(attack_target)

    @staticmethod
    def get_target_from_in_range_enemies(in_range_enemies: Units) -> Unit:
        """We get the queen_control to prioritise in range flying units"""
        if in_range_enemies.flying:
            lowest_hp: Unit = min(
                in_range_enemies.flying,
                key=lambda e: (e.health + e.shield, e.tag),
            )
        else:
            lowest_hp: Unit = min(
                in_range_enemies,
                key=lambda e: (e.health + e.shield, e.tag),
            )
        return lowest_hp

    def get_transfuse_target(
        self, from_pos: Point2, targets_being_transfused: Dict[int, float]
    ) -> Optional[Unit]:
        transfuse_targets: Units = self.kd_trees.own_units_in_range_of_point(
            from_pos, 11.0
        ).filter(
            lambda unit: unit.tag not in targets_being_transfused
            and unit.type_id in UNITS_TO_TRANSFUSE
            and unit.health_percentage < 0.5
        )

        return transfuse_targets.closest_to(from_pos) if transfuse_targets else None

    # noinspection PyMethodMayBeStatic
    def get_turn_speed(self) -> float:
        """Returns turn speed of unit in radians"""
        return QUEEN_TURN_RATE * 1.4 * math.pi / 180

    def position_near_enemy(self, pos: Point2) -> bool:
        return (
            self.kd_trees.enemy_units_in_range_of_point(pos, 12.0)
            .filter(
                lambda unit: unit.can_attack_ground
                and unit.type_id not in EXCLUDE_FROM_POS_NEAR_ENEMY
            )
            .amount
            > 0
        )

    def position_near_enemy_townhall(self, pos: Point2) -> bool:
        close_townhalls: Units = self.bot.enemy_structures.filter(
            lambda unit: unit.type_id in GROUND_TOWNHALL_TYPES
            and unit.distance_to(pos) < 20
        )
        return close_townhalls.amount > 0

    @staticmethod
    def is_position_safe(
        grid: np.ndarray,
        position: Point2,
        weight_safety_limit: float = 1.0,
    ) -> bool:
        """
        Checks if the current position is dangerous by comparing against default_grid_weights
        @param grid: Grid we want to check
        @param position: Position of the unit etc
        @param weight_safety_limit: The threshold at which we declare the position safe
        @return:
        """
        position = position.rounded
        weight: float = grid[position.x, position.y]
        # np.inf check if drone is pathing near a spore crawler
        return weight == np.inf or weight <= weight_safety_limit

    def find_closest_safe_spot(
        self, from_pos: Point2, grid: np.ndarray, radius: int = 15
    ) -> Point2:
        all_safe: np.ndarray = self.map_data.lowest_cost_points_array(
            from_pos, radius, grid
        )
        # type hint wants a numpy array but doesn't actually need one - this is faster
        all_dists = spatial.distance.cdist(all_safe, [from_pos], "sqeuclidean")
        min_index = np.argmin(all_dists)

        # safe because the shape of all_dists (N x 1) means argmin will return an int
        return Point2(all_safe[min_index])

    def move_towards_safe_spot(
        self, unit: Unit, grid: np.ndarray, radius: int = 7
    ) -> None:
        if self.map_data:
            safe_spot: Point2 = self.find_closest_safe_spot(unit.position, grid, radius)
            path: List[Point2] = self.map_data.pathfind(
                unit.position, safe_spot, grid, sensitivity=2
            )
            if path:
                unit.move(path[0])
        else:
            unit.move(self.bot.start_location)

    # noinspection PyMethodMayBeStatic
    def range_vs_target(self, unit, target) -> float:
        """Get the range of a unit to a target."""
        if unit.can_attack_air and target.is_flying:
            return unit.air_range
        else:
            return unit.ground_range

    def find_closest_enemy(self, unit: Unit, enemies: Units) -> Optional[Unit]:
        """
        Find closest enemy because the built in python-sc2 version doesn't work with memory units.

        @param unit:
        @param enemies:
        @return:
        """
        if not unit or not enemies:
            return None

        distances = spatial.distance.cdist(
            np.array([e.position for e in enemies]),
            np.array([unit.position]),
            "sqeuclidean",
        )

        closest_enemy = min(
            ((unit, dist) for unit, dist in zip(enemies, distances)),
            key=lambda my_tuple: my_tuple[1],
        )[0]

        return closest_enemy

    def _find_closest_to_target(self, target_pos: Point2, grid: np.ndarray) -> Point2:
        try:
            nearest_spot = grid[
                np.sum(
                    np.square(np.abs(grid - np.array([[target_pos.x, target_pos.y]]))),
                    1,
                ).argmin()
            ]

            pos = Point2(Pointlike((nearest_spot[0], nearest_spot[1])))
            return pos
        except ValueError:
            return target_pos.towards(self.bot.start_location, 1)

    @staticmethod
    def get_random_position_from(from_position: Point2, distance: int):
        """Start at a position and get a random new position `distance` away"""
        angle: int = randint(0, 360)
        return from_position + (distance * Point2((cos(angle), sin(angle))))

    def position_blocks_expansion(self, position: Point2) -> bool:
        """Will the creep tumor block expansion"""
        blocks_expansion: bool = False
        for expansion in self.bot.expansion_locations_list:
            if position.distance_to(expansion) < 5.0:
                blocks_expansion = True
                break
        return blocks_expansion
