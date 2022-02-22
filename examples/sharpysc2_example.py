import random
from typing import Optional, List

from sharpy.knowledges import KnowledgeBot
from sharpy.plans import BuildOrder, SequentialList, Step
from sharpy.plans.acts import ActUnit, ActBuilding, Expand
from sharpy.plans.acts.zerg import AutoOverLord
from sharpy.plans.tactics import DistributeWorkers, SpeedMining

from queens_sc2.consts import QueenRoles
from queens_sc2.sharpy import QueensSc2Manager, SetQueensSc2Policy
from sc2 import maps
from sc2.data import Race, Difficulty
from sc2.ids.unit_typeid import UnitTypeId
from sc2.main import run_game
from sc2.player import Bot, Computer


class SharpyExample(KnowledgeBot):
    """An example sharpy bot"""

    def configure_managers(self) -> Optional[List["ManagerBase"]]:
        return [QueensSc2Manager(use_sc2_map_analyzer=True)]

    async def create_plan(self) -> BuildOrder:
        queens_manager = self.knowledge.get_manager(QueensSc2Manager)

        # Policies originally from QueenBot: https://aiarena.net/bots/201/
        early_game_queen_policy = {
            "creep_queens": {
                "active": True,
                "distance_between_queen_tumors": 3,
                "first_tumor_position": self.zone_manager.own_natural.center_location.towards(
                    self.game_info.map_center, 9
                ),
                "priority": True,
                "prioritize_creep": lambda: True,
                "max": 2,
                "defend_against_ground": True,
                "rally_point": self.zone_manager.own_natural.center_location,
                "priority_defence_list": {
                    UnitTypeId.ZERGLING,
                    UnitTypeId.MARINE,
                    UnitTypeId.ZEALOT
                },
            },
            "creep_dropperlord_queens": {
                "active": True,
                "priority": True,
                "max": 1,
                "pass_own_threats": True,
                "target_expansions": [
                    el[0] for el in self.expansion_locations_list[-6:-3]
                ],
            },
            "defence_queens": {
                "attack_condition": lambda: self.enemy_units.filter(
                    lambda u: u.type_id == UnitTypeId.WIDOWMINEBURROWED
                              and u.distance_to(self.enemy_start_locations[0]) > 50
                              and not queens_manager.queens.defence.enemy_air_threats
                              and not queens_manager.queens.defence.enemy_ground_threats
                )
                                            or (
                                                    self.structures(UnitTypeId.NYDUSCANAL)
                                                    and self.units(UnitTypeId.QUEEN).amount > 25
                                            ),
                "rally_point": self.zone_manager.own_natural.center_location,
            },
            "inject_queens": {"active": False},
            "nydus_queens": {
                "active": True,
                "max": 12,
                "steal_from": {QueenRoles.Defence},
            },
        }

        mid_game_queen_policy = {
            "creep_queens": {
                "max": 2,
                "priority": True,
                "defend_against_ground": True,
                "distance_between_queen_tumors": 3,
                "priority_defence_list": {
                    UnitTypeId.BATTLECRUISER,
                    UnitTypeId.LIBERATOR,
                    UnitTypeId.LIBERATORAG,
                    UnitTypeId.VOIDRAY,
                },
            },
            "creep_dropperlord_queens": {
                "active": True,
                "priority": True,
                "max": 1,
                "pass_own_threats": True,
                "priority_defence_list": set(),
                "target_expansions": [
                    el for el in self.expansion_locations_list
                ],
            },
            "defence_queens": {
                "attack_condition": lambda: (
                                                    sum([unit.energy for unit in self.units(UnitTypeId.QUEEN)])
                                                    / self.units(UnitTypeId.QUEEN).amount
                                                    >= 75
                                                    and self.units(UnitTypeId.QUEEN).amount > 40
                                            )
                                            or self.enemy_units.filter(
                    lambda u: u.type_id == UnitTypeId.WIDOWMINEBURROWED
                              and u.distance_to(self.enemy_start_locations[0]) > 50
                              and not queens_manager.queens.defence.enemy_air_threats
                              and not queens_manager.queens.defence.enemy_ground_threats
                )
                                            or self.structures(UnitTypeId.NYDUSCANAL),
                "rally_point": self.zone_manager.own_natural.center_location,
            },
            "inject_queens": {"active": False},
            "nydus_queens": {
                "active": True,
                "max": 12,
                "steal_from": {QueenRoles.Defence},
            },
        }

        build_drones = lambda ai: self.workers.amount >= self.townhalls.amount * 16 \
                                  or self.workers.amount >= 16 * 3  # max 3 base saturation
        return BuildOrder(
            SetQueensSc2Policy(early_game_queen_policy, policy_name="early_game_queen_policy"),
            ActUnit(UnitTypeId.DRONE, UnitTypeId.LARVA, 13),
            ActUnit(UnitTypeId.OVERLORD, UnitTypeId.LARVA, 1),
            ActUnit(UnitTypeId.DRONE, UnitTypeId.LARVA, 14),
            Expand(2),
            ActUnit(UnitTypeId.DRONE, UnitTypeId.LARVA, 16),
            ActBuilding(UnitTypeId.SPAWNINGPOOL, 1),
            ActUnit(UnitTypeId.OVERLORD, UnitTypeId.LARVA, 2),
            SequentialList(
                Step(None, SetQueensSc2Policy(mid_game_queen_policy, policy_name="mid_game_queen_policy"),
                     skip_until=lambda ai: ai.time > 480),
                Step(None, DistributeWorkers(max_gas=0), skip=lambda ai: ai.time > 480),
                Step(None, DistributeWorkers(max_gas=0),
                     skip_until=lambda ai: ai.time > 480 and self.knowledge.iteration % 4 == 0),
                Step(None, SpeedMining(), lambda ai: ai.client.game_step > 5),
                AutoOverLord(),
                BuildOrder(
                    Step(None, ActUnit(UnitTypeId.DRONE, UnitTypeId.LARVA), skip=build_drones),
                    Step(None, ActUnit(UnitTypeId.QUEEN, UnitTypeId.HATCHERY)),
                    Expand(4),  # 4 mining bases
                    ActBuilding(UnitTypeId.HATCHERY, 40),  # Macro hatcheries - 20 includes mining bases
                )
            ),
        )


if __name__ == "__main__":
    # Local game
    random_map = random.choice(["2000AtmospheresAIE"])
    random_race = random.choice([Race.Zerg, Race.Terran, Race.Protoss])
    bot = Bot(Race.Zerg, SharpyExample('SharpyExample'))
    run_game(
        maps.get(random_map),
        [bot, Computer(Race.Terran, Difficulty.VeryHard)],
        realtime=False,
    )
