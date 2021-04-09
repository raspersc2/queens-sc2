import math
from abc import ABC, abstractmethod
from typing import Dict, Optional, Set, Union

import numpy as np
from sc2 import BotAI
from sc2.constants import UNIT_COLOSSUS
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units
from scipy import spatial

from queens_sc2.cache import property_cache_once_per_frame
from queens_sc2.policy import Policy

QUEEN_TURN_RATE: float = 999.8437
UNITS_TO_TRANSFUSE: Set[UnitID] = {
    UnitID.BROODLORD,
    UnitID.CORRUPTOR,
    UnitID.HYDRALISK,
    UnitID.LURKER,
    UnitID.MUTALISK,
    UnitID.QUEEN,
    UnitID.RAVAGER,
    UnitID.ROACH,
    UnitID.OVERSEER,
    UnitID.OVERLORD,
    UnitID.SWARMHOSTMP,
    UnitID.ULTRALISK,
    UnitID.SPINECRAWLER,
    UnitID.SPORECRAWLER,
    UnitID.HATCHERY,
    UnitID.LAIR,
    UnitID.HIVE,
    UnitID.VIPER,
    UnitID.INFESTOR,
    UnitID.SPAWNINGPOOL,
    UnitID.NYDUSCANAL,
    UnitID.NYDUSNETWORK,
}


class BaseUnit(ABC):
    policy: Policy

    def __init__(self, bot: BotAI, map_data: "MapData"):
        self.bot: BotAI = bot
        self.map_data: Optional["MapData"] = map_data

    @property_cache_once_per_frame
    def enemy_air_threats(self) -> Units:
        air_threats: Units = Units([], self.bot)
        air_units: Units = self.bot.enemy_units.flying
        threats: Units = Units([], self.bot)
        if air_units:
            for th in self.bot.townhalls.ready:
                closest_enemy: Unit = air_units.closest_to(th)
                if closest_enemy.position.distance_to(th) < 18:
                    air_threats.extend(
                        self.bot.enemy_units.filter(
                            lambda unit: unit.is_flying
                            and not unit.is_hallucination
                            and unit.type_id
                            not in {UnitID.OVERLORD, UnitID.OVERSEER, UnitID.OBSERVER}
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
                            and unit.type_id
                            not in {
                                UnitID.CHANGELING,
                                UnitID.CHANGELINGMARINE,
                                UnitID.CHANGELINGMARINESHIELD,
                                UnitID.CHANGELINGZEALOT,
                                UnitID.CHANGELINGZERGLING,
                                UnitID.CHANGELINGZERGLINGWINGS,
                            }
                        )
                    )
            threats = ground_threats
        return threats

    @abstractmethod
    async def handle_unit(
        self,
        air_threats_near_bases: Units,
        ground_threats_near_bases: Units,
        priority_enemy_units: Units,
        unit: Unit,
        th_tag: int = 0,
        grid: Optional[np.ndarray] = None,
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

    async def do_queen_micro(self, queen: Unit, enemy: Units) -> None:
        if not queen:
            return

        in_range_enemies: Units = self.bot.enemy_units.in_attack_range_of(queen)
        in_range_enemies = in_range_enemies.exclude_type({UnitID.EGG, UnitID.LARVA})
        if in_range_enemies:
            target: Unit = self._get_target_from_in_range_enemies(in_range_enemies)
            if self.attack_ready(queen, target):
                queen.attack(target)
            else:
                distance: float = queen.ground_range + queen.radius + target.radius
                move_to: Point2 = target.position.towards(queen, distance)
                if self.bot.in_pathing_grid(move_to):
                    queen.move(move_to)

        elif enemy:
            target = enemy.closest_to(queen)
            queen.attack(target)
        elif self.bot.all_enemy_units:
            target = self.bot.all_enemy_units.closest_to(queen)
            queen.attack(target)

    async def do_queen_offensive_micro(
        self, queen: Unit, offensive_pos: Point2
    ) -> None:
        if not queen or not offensive_pos:
            return
        enemy: Units = self.bot.enemy_units.exclude_type(
            {UnitID.MULE, UnitID.EGG, UnitID.LARVA}
        )
        enemy_structures: Units = self.bot.enemy_structures
        queens: Units = self.bot.units(UnitID.QUEEN)
        own_close_queens: Units = queens.filter(lambda u: u.distance_to(queen) < 5)
        if enemy:
            in_range_enemies: Units = enemy.in_attack_range_of(queen)
            in_range_structures: Units = enemy_structures.in_attack_range_of(queen)
            if in_range_enemies:
                target: Unit = self._get_target_from_in_range_enemies(in_range_enemies)
                if self.attack_ready(queen, target):
                    queen.attack(target)
                else:
                    # loose queens should try to rejoin the queen pack
                    if own_close_queens.amount <= 3:
                        queen.move(queens.center)
                    # otherwise move forward between attacks, since Queen is slow and can get stuck behind each other
                    else:
                        queen.move(offensive_pos)
            elif in_range_structures:
                target: Unit = self._get_target_from_in_range_enemies(
                    in_range_structures
                )
                if self.attack_ready(queen, target):
                    queen.attack(target)
                else:
                    if own_close_queens.amount <= 3:
                        queen.move(queens.center)
                    else:
                        queen.move(offensive_pos)
            else:
                queen.move(offensive_pos)

        else:
            queen.attack(offensive_pos)

    def _get_target_from_in_range_enemies(self, in_range_enemies: Units) -> Unit:
        """ We get the queens to prioritise in range flying units """
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
        # unit tags that have already been transfused recently
        active_transfuse_target_tags = targets_being_transfused.keys()
        transfuse_targets: Units = self.bot.all_own_units.filter(
            lambda unit: unit.health_percentage < 0.4
            and unit.tag not in active_transfuse_target_tags
            and unit.type_id in UNITS_TO_TRANSFUSE
            and unit.distance_to(from_pos) < 11
        )

        return transfuse_targets.closest_to(from_pos) if transfuse_targets else None

    # noinspection PyMethodMayBeStatic
    def get_turn_speed(self) -> float:
        """Returns turn speed of unit in radians"""
        return QUEEN_TURN_RATE * 1.4 * math.pi / 180

    def position_near_enemy(self, pos: Point2) -> bool:
        close_enemy: Units = self.bot.enemy_units.filter(
            lambda unit: unit.position.distance_to(pos) < 12
            and unit.can_attack_ground
            and unit.type_id
            not in {
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
        )
        return True if close_enemy else False

    def position_near_enemy_townhall(self, pos: Point2) -> bool:
        close_townhalls: Units = self.bot.enemy_structures.filter(
            lambda unit: unit.type_id
            in {
                UnitID.HATCHERY,
                UnitID.HIVE,
                UnitID.LAIR,
                UnitID.NEXUS,
                UnitID.COMMANDCENTER,
                UnitID.ORBITALCOMMAND,
                UnitID.PLANETARYFORTRESS,
            }
            and unit.distance_to(pos) < 20
        )
        return True if close_townhalls else False

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

    def in_attack_range_of(
        self, unit: Unit, enemies: Units, bonus_distance: Union[int, float] = 0
    ) -> Optional[Units]:
        """
        Get enemies in attack range of a given unit

        @param unit:
        @param enemies:
        @param bonus_distance:
        @return:
        """
        if not unit or not enemies:
            return None

        return enemies.filter(
            lambda e: self.target_in_range(unit, e, bonus_distance=bonus_distance)
        )

    def target_in_range(
        self, unit: Unit, target: Unit, bonus_distance: Union[int, float] = 0
    ) -> bool:
        """
        Check if the target is in range. Includes the target's radius when calculating distance to target.

        @param unit:
        @param target:
        @param bonus_distance:
        @return:
        """
        if unit.can_attack_ground and not target.is_flying:
            unit_attack_range = unit.ground_range
        elif unit.can_attack_air and (
            target.is_flying or target.type_id == UNIT_COLOSSUS
        ):
            unit_attack_range = unit.air_range
        else:
            return False

        # noinspection PyProtectedMember
        return self.bot._distance_pos_to_pos(unit.position, target.position) <= (
            unit.radius + target.radius + unit_attack_range + bonus_distance
        )
