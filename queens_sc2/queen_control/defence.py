from typing import Optional, Set

import numpy as np

from sc2.bot_ai import BotAI
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from queens_sc2.kd_trees import KDTrees
from queens_sc2.queen_control.base_unit import BaseUnit
from queens_sc2.policy import Policy


class Defence(BaseUnit):
    def __init__(
        self,
        bot: BotAI,
        kd_trees: KDTrees,
        defence_policy: Policy,
        map_data: Optional["MapData"],
    ):
        super().__init__(bot, kd_trees, map_data)
        self.policy = defence_policy

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
        if self.keep_queen_safe(avoidance_grid, grid, unit):
            return
        if priority_enemy_units:
            self.do_queen_micro(
                unit, priority_enemy_units, grid, attack_static_defence=False
            )
        elif self.policy.attack_condition():
            self.do_queen_offensive_micro(unit, self.policy.attack_target, queens)
        elif self.bot.enemy_units and self.kd_trees.get_enemies_in_attack_range_of(
            unit
        ):
            self.do_queen_micro(
                unit, self.bot.enemy_units, grid, attack_static_defence=False
            )
        elif self.policy.defend_against_ground and ground_threats_near_bases:
            self.do_queen_micro(
                unit, ground_threats_near_bases, grid, attack_static_defence=False
            )
        elif self.policy.defend_against_air and air_threats_near_bases:
            self.do_queen_micro(unit, air_threats_near_bases, grid)
        elif (
            self.map_data
            and grid is not None
            and not self.is_position_safe(grid, unit.position)
        ):
            self.move_towards_safe_spot(unit, grid)
        elif unit.tag not in in_range_of_rally_tags:
            unit.move(self.policy.rally_point)

    def set_attack_target(self, target: Point2) -> None:
        """
        Set an attack target if defence queen_control are going to be offensive
        """
        self.policy.attack_target = target

    def set_rally_point(self, rally_point: Point2) -> None:
        self.policy.rally_point = rally_point

    def update_policy(self, policy: Policy) -> None:
        self.policy = policy
