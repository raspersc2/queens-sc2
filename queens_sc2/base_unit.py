from abc import ABC, abstractmethod
from typing import Optional, Union

import numpy as np
from scipy import spatial

from sc2 import BotAI
from sc2.constants import UNIT_COLOSSUS
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from queens_sc2.policy import Policy
from queens_sc2.cache import property_cache_once_per_frame


class BaseUnit(ABC):
    policy: Policy

    def __init__(self, bot: BotAI):
        self.bot: BotAI = bot

    @property_cache_once_per_frame
    def enemy_air_threats(self) -> Units:
        air_threats: Units = Units([], self.bot)
        air_units: Units = self.bot.enemy_units.flying
        threats: Units = Units([], self.bot)
        if air_units:
            for th in self.bot.townhalls.ready:
                closest_enemy: Unit = self.find_closest_enemy(th, air_units)
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
        ground_units: Units = self.bot.enemy_units.not_flying
        threats: Units = Units([], self.bot)
        if ground_units:
            for th in self.bot.townhalls.ready:
                closest_enemy: Unit = self.find_closest_enemy(th, ground_units)
                if closest_enemy.position.distance_to(th) < 18:
                    ground_threats.extend(
                        self.bot.enemy_units.filter(
                            lambda unit: not unit.is_flying
                            and not unit.is_hallucination
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

    def get_priority_enemy_units(self, enemy_threats: Units) -> Optional[Units]:
        if len(self.policy.priority_defence_list) != 0:
            priority_threats: Units = enemy_threats(self.policy.priority_defence_list)
            return priority_threats

    @abstractmethod
    async def handle_unit(
        self,
        air_threats_near_bases: Units,
        ground_threats_near_bases: Units,
        unit: Unit,
        priority_enemy_units: Units,
        th_tag: int,
    ) -> None:
        pass

    @abstractmethod
    def update_policy(self, policy: Policy) -> None:
        pass

    async def do_queen_micro(self, queen: Unit, enemy: Units) -> None:
        if not queen or not enemy:
            return
        in_range_enemies: Units = self.in_attack_range_of(queen, enemy)
        if in_range_enemies:
            if queen.weapon_cooldown == 0:
                lowest_hp: Unit = min(
                    in_range_enemies, key=lambda e: (e.health + e.shield, e.tag)
                )
                queen.attack(lowest_hp)
            else:
                closest_enemy: Unit = self.find_closest_enemy(queen, in_range_enemies)
                distance: float = (
                    queen.ground_range + queen.radius + closest_enemy.radius
                )

                queen.move(closest_enemy.position.towards(queen, distance))

        else:
            target = self.find_closest_enemy(queen, enemy)
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
            in_range_enemies: Units = self.in_attack_range_of(queen, enemy)
            in_range_structures: Units = self.in_attack_range_of(
                queen, enemy_structures
            )
            if queen.weapon_cooldown == 0:
                if in_range_enemies:
                    lowest_hp: Unit = min(
                        in_range_enemies, key=lambda e: (e.health + e.shield, e.tag)
                    )
                    queen.attack(lowest_hp)
                elif in_range_structures:
                    queen.attack(self.find_closest_enemy(queen, in_range_structures))
                else:
                    queen.move(offensive_pos)
            else:
                if own_close_queens.amount <= 3:
                    queen.move(queens.center)
                else:
                    queen.move(offensive_pos)
        else:
            queen.attack(offensive_pos)

    def get_transfuse_target(self, from_pos: Point2) -> Optional[Unit]:
        transfuse_targets: Units = self.bot.units.filter(
            lambda unit: unit.health_percentage < 0.4
            and unit.type_id
            in {
                UnitID.BROODLORD,
                UnitID.CORRUPTOR,
                UnitID.HYDRALISK,
                UnitID.LURKER,
                UnitID.MUTALISK,
                UnitID.QUEEN,
                UnitID.RAVAGER,
                UnitID.ROACH,
                UnitID.SWARMHOSTMP,
                UnitID.ULTRALISK,
            }
            and unit.distance_to(from_pos) < 11
        ) + self.bot.structures.filter(
            lambda s: s.health_percentage < 0.4
            and s.type_id in {UnitID.SPINECRAWLER, UnitID.SPORECRAWLER}
            and s.distance_to(from_pos) < 11
        )

        return transfuse_targets.closest_to(from_pos) if transfuse_targets else None

    def position_near_enemy(self, pos: Point2) -> bool:
        close_enemy: Units = self.bot.enemy_units.filter(
            lambda unit: unit.position.distance_to(pos) < 12
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
