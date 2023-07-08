from typing import Optional, Set

import numpy as np

from sc2.bot_ai import BotAI
from sc2.ids.ability_id import AbilityId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from queens_sc2.kd_trees import KDTrees
from queens_sc2.queen_control.base_unit import BaseUnit
from queens_sc2.policy import Policy


class Inject(BaseUnit):
    def __init__(
        self,
        bot: BotAI,
        kd_trees: KDTrees,
        inject_policy: Policy,
        map_data: Optional["MapData"],
    ):
        super().__init__(bot, kd_trees, map_data)
        self.policy = inject_policy

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
        ths: Units = self.bot.townhalls.filter(lambda u: u.is_ready and u.tag == th_tag)
        if ths:
            th: Unit = ths.first
            if priority_enemy_units:
                self.do_queen_micro(
                    unit, priority_enemy_units, grid, attack_static_defence=False
                )
            elif self.policy.defend_against_ground and ground_threats_near_bases:
                self.do_queen_micro(
                    unit, ground_threats_near_bases, grid, attack_static_defence=False
                )
            elif self.policy.defend_against_air and air_threats_near_bases:
                self.do_queen_micro(
                    unit, air_threats_near_bases, grid, attack_static_defence=False
                )
            else:
                in_attack_range: Units = self.kd_trees.get_enemies_in_attack_range_of(
                    unit
                )
                target: Optional[Unit] = None
                if in_attack_range:
                    target = self.get_target_from_in_range_enemies(in_attack_range)

                if target and self.attack_ready(unit, target):
                    unit.attack(target)
                elif unit.energy >= 25:
                    unit(AbilityId.EFFECT_INJECTLARVA, th)
                # control the queen between injects
                else:
                    self._control_inject_queen_near_base(
                        air_threats_near_bases,
                        ground_threats_near_bases,
                        unit,
                        th,
                        grid,
                        natural_position,
                    )

    def update_policy(self, policy: Policy) -> None:
        self.policy = policy

    def _control_inject_queen_near_base(
        self,
        air_threats_near_bases: Units,
        ground_threats_near_bases: Units,
        queen: Unit,
        townhall: Unit,
        grid: Optional[np.ndarray] = None,
        natural_position: Optional[Point2] = None,
    ) -> None:
        """
        Between injects, we want the Queen to have the following behavior:
        - Attack any enemy that gets too close
        - Move the Queen back if she goes too far from the townhall
        - Stay out of the mineral line, incase bot has custom mineral gathering (don't block workers)
        """

        close_threats: Units = Units([], self.bot)
        # we can only have close threats if enemy are near our bases in the first place
        # so save calculation otherwise
        if air_threats_near_bases or ground_threats_near_bases:
            close_threats = self.bot.enemy_units.filter(
                lambda enemy: enemy.position.distance_to(townhall) < 13
            )

        # prevent queen wondering off is priority
        if queen.distance_to(townhall) > 12.5:
            queen.move(townhall)

        elif close_threats:
            self.do_queen_micro(queen, close_threats, grid)

        # every now and then, check queen is not in the mineral field blocking workers
        elif self.bot.state.game_loop % 32 == 0:
            close_mfs: Units = self.bot.mineral_field.filter(
                lambda mf: mf.distance_to(townhall) < 8
            )
            # make a small adjustment away from the minerals
            if close_mfs and queen.distance_to(close_mfs.center) < 6:
                queen.move(queen.position.towards(close_mfs.center, -1))
