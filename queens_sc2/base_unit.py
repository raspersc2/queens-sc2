from abc import ABC, abstractmethod
from typing import Optional

from sc2 import BotAI
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from queens_sc2.policy import Policy


class BaseUnit(ABC):
    policy: Policy

    def __init__(self, bot: BotAI):
        self.bot: BotAI = bot

    @property
    def enemy_air_threats(self) -> Units:
        air_threats: Units = Units([], self.bot)
        ready_townhalls: Units = self.bot.townhalls.ready

        if ready_townhalls:
            for th in ready_townhalls:
                air_threats.extend(
                    self.bot.enemy_units.filter(
                        lambda unit: unit.is_flying
                        and not unit.is_hallucination
                        and unit.type_id
                        not in {UnitID.OVERLORD, UnitID.OVERSEER, UnitID.OBSERVER}
                        and unit.distance_to(th) < 18
                    )
                )

        return air_threats

    @property
    def enemy_ground_threats(self) -> Units:
        ground_threats: Units = Units([], self.bot)
        ready_townhalls: Units = self.bot.townhalls.ready

        if ready_townhalls:
            for th in ready_townhalls:
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
                        and unit.position.distance_to(th) < 18
                    )
                )

        return ground_threats

    @property
    def priority_enemy_units(self) -> Optional[Units]:
        if len(self.policy.priority_defence_list) != 0:
            all_threats: Units = self.enemy_air_threats + self.enemy_ground_threats
            priority_threats: Units = all_threats(self.policy.priority_defence_list)
            return priority_threats

    @abstractmethod
    async def handle_unit(
        self,
        air_threats_near_bases: Units,
        ground_threats_near_bases: Units,
        unit: Unit,
        th_tag: int,
    ) -> None:
        pass

    @abstractmethod
    def update_policy(self, policy: Policy) -> None:
        pass

    async def do_queen_micro(self, queen: Unit, enemy: Units) -> None:
        if not queen or not enemy:
            return
        in_range_enemies: Units = enemy.in_attack_range_of(queen)
        if in_range_enemies:
            if queen.weapon_cooldown == 0:
                lowest_hp: Unit = min(
                    in_range_enemies, key=lambda e: (e.health + e.shield, e.tag)
                )
                queen.attack(lowest_hp)
            else:
                closest_enemy: Unit = in_range_enemies.closest_to(queen)
                distance: float = (
                    queen.ground_range + queen.radius + closest_enemy.radius
                )

                queen.move(closest_enemy.position.towards(queen, distance))

        else:
            queen.attack(enemy.center)

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
            if queen.weapon_cooldown == 0:
                if in_range_enemies:
                    lowest_hp: Unit = min(
                        in_range_enemies, key=lambda e: (e.health + e.shield, e.tag)
                    )
                    queen.attack(lowest_hp)
                elif in_range_structures:
                    queen.attack(in_range_structures.closest_to(queen))
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
            lambda unit: unit.distance_to(pos) < 12
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
