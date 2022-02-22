import random
from typing import Dict

import numpy as np

from queens_sc2.queens import Queens
from sharpy.events import UnitDestroyedEvent
from sharpy.managers import ManagerBase

from sc2.position import Point2


class QueensSc2Manager(ManagerBase):
    """
    A basic custom sharpy manager to utilize queens-sc2 in the context of a sharpy bot.

    Requires sharpy to be already be installed: https://github.com/DrInfy/sharpy-sc2
    ManagerBase is from https://github.com/DrInfy/sharpy-sc2/blob/develop/sharpy/managers/core/manager_base.py
    """

    def __init__(self, queen_policy: Dict = None, use_sc2_map_analyzer=False, auto_manage_attack_target=True):
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
            self.air_grid = map_data.get_clean_air_grid()
        else:
            self.ground_grid = None
            self.air_grid = None

        self.queens = Queens(self.ai, debug=self.debug, queen_policy=self.queen_policy)

        knowledge.register_on_unit_destroyed_listener(self.on_unit_destroyed)

    async def update(self):

        if self.auto_manage_attack_target:
            self.update_attack_target(await self._find_attack_position(self.ai))

        # depending on usecase it may not need a fresh grid every step
        await self.queens.manage_queens(self.knowledge.iteration, air_grid=self.air_grid, grid=self.ground_grid)

    async def post_update(self):
        pass

    def set_new_policy(self, queen_policy: Dict):
        self.queens.set_new_policy(queen_policy)

    def update_attack_target(self, attack_target: Point2):
        self.queens.update_attack_target(attack_target)

    # Extracted from sharpy's PlanFinishEnemy act
    async def _find_attack_position(self, ai):
        main_pos = self.zone_manager.own_main_zone.center_location

        target = random.choice(list(ai.expansion_locations_list))
        last_distance2 = target.distance_to(main_pos)
        target_known = False
        if ai.enemy_structures.exists:
            for building in ai.enemy_structures:
                if building.health > 0:
                    current_distance2 = target.distance_to(main_pos)
                    if not target_known or current_distance2 < last_distance2:
                        target = building.position
                        last_distance2 = current_distance2
                        target_known = True
        return target
