from typing import Dict

import numpy as np
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.units import Units
from sharpy.events import UnitDestroyedEvent
from sharpy.managers import ManagerBase

from queens_sc2.queens import Queens


class QueensSc2Manager(ManagerBase):
    """
    A basic custom sharpy manager to utilize queens-sc2 in the context of a sharpy bot.

    Requires sharpy to be already be installed: https://github.com/DrInfy/sharpy-sc2
    ManagerBase is from https://github.com/DrInfy/sharpy-sc2/blob/develop/sharpy/managers/core/manager_base.py
    """

    def __init__(
        self,
        queen_policy: Dict = None,
        use_sc2_map_analyzer=False,
        auto_manage_attack_target=True,
    ):
        super().__init__()
        self.queen_policy = queen_policy
        self.queens = None
        self.use_sc2_map_analyzer = use_sc2_map_analyzer
        self.auto_manage_attack_target = auto_manage_attack_target

    def on_unit_destroyed(self, event: UnitDestroyedEvent):
        self.queens.remove_unit(event.unit)

    async def start(self, knowledge: "Knowledge"):
        await super().start(knowledge)

        if self.use_sc2_map_analyzer:
            from MapAnalyzer import MapData

            map_data = MapData(self.ai)
            self.ground_grid: np.ndarray = map_data.get_pyastar_grid()
            self.avoidance_grid: np.ndarray = map_data.get_pyastar_grid()
            self.air_grid = map_data.get_clean_air_grid()
        else:
            self.ground_grid = None
            self.air_grid = None

        self.queens = Queens(self.ai, debug=self.debug, queen_policy=self.queen_policy)

        knowledge.register_on_unit_destroyed_listener(self.on_unit_destroyed)

    async def update(self):
        if self.auto_manage_attack_target:
            self.update_attack_target(await self._find_attack_position())

        # depending on usecase it may not need a fresh grid every step
        await self.queens.manage_queens(
            self.knowledge.iteration,
            air_grid=self.air_grid,
            avoidance_grid=self.avoidance_grid,
            grid=self.ground_grid,
        )

    async def post_update(self):
        pass

    def set_new_policy(self, queen_policy: Dict):
        self.queens.set_new_policy(queen_policy)

    def update_attack_target(self, attack_target: Point2):
        self.queens.update_attack_target(attack_target)

    # Extracted from sharpy's PlanFinishEnemy act
    async def _find_attack_position(self):
        enemy_units: Units = self.ai.enemy_units.filter(
            lambda u: u.type_id
            not in {
                UnitTypeId.SCV,
                UnitTypeId.DRONE,
                UnitTypeId.PROBE,
                UnitTypeId.MULE,
                UnitTypeId.LARVA,
                UnitTypeId.EGG,
                UnitTypeId.CHANGELING,
                UnitTypeId.CHANGELINGZERGLING,
                UnitTypeId.CHANGELINGZERGLINGWINGS,
                UnitTypeId.REAPER,
            }
            and not u.is_flying
        )
        enemy_structures: Units = self.ai.enemy_structures
        if enemy_units:
            return enemy_units.closest_to(self.ai.start_location).position
        elif enemy_structures:
            return enemy_structures.closest_to(self.ai.start_location).position
        else:
            return self.ai.enemy_start_locations[0]
