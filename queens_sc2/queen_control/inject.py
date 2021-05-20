from typing import Optional

import numpy as np
from sc2 import BotAI
from sc2.ids.ability_id import AbilityId
from sc2.unit import Unit
from sc2.units import Units

from queens_sc2.queen_control.base_unit import BaseUnit
from queens_sc2.policy import Policy


class Inject(BaseUnit):
    def __init__(
        self, bot: BotAI, inject_policy: Policy, map_data: Optional["MapData"]
    ):
        super().__init__(bot, map_data)
        self.policy = inject_policy

    async def handle_unit(
        self,
        air_threats_near_bases: Units,
        ground_threats_near_bases: Units,
        priority_enemy_units: Units,
        unit: Unit,
        th_tag: int = 0,
        grid: Optional[np.ndarray] = None,
    ) -> None:

        ths: Units = self.bot.townhalls.ready.tags_in([th_tag])
        if ths:
            th: Unit = ths.first
            if priority_enemy_units:
                await self.do_queen_micro(unit, priority_enemy_units)
            elif self.policy.defend_against_air and air_threats_near_bases:
                await self.do_queen_micro(unit, air_threats_near_bases)
            elif self.policy.defend_against_ground and ground_threats_near_bases:
                await self.do_queen_micro(unit, ground_threats_near_bases)
            else:
                if unit.energy >= 25:
                    unit(AbilityId.EFFECT_INJECTLARVA, th)
                # control the queen between injects
                else:
                    await self._control_inject_queen_near_base(
                        air_threats_near_bases, ground_threats_near_bases, unit, th
                    )

    def update_policy(self, policy: Policy) -> None:
        self.policy = policy

    async def _control_inject_queen_near_base(
        self,
        air_threats_near_bases: Units,
        ground_threats_near_bases: Units,
        queen: Unit,
        townhall: Unit,
    ) -> None:
        """
        Between injects, we want the Queen to have the following behavior:
        - Attack any enemy that gets too close
        - Move the Queen back if she goes too far from the townhall
        - Stay out of the mineral line, incase bot has custom mineral gathering (don't block workers)
        """
        # don't do anything else, just move the queen back
        if queen.distance_to(townhall) > 7:
            queen.move(townhall)
            return

        close_threats: Units = Units([], self.bot)
        # we can only have close threats if enemy are near our bases in the first place
        # so save calculation otherwise
        if air_threats_near_bases or ground_threats_near_bases:
            close_threats = self.bot.enemy_units.filter(
                lambda enemy: enemy.position.distance_to(townhall) < 10
            )

        if close_threats:
            await self.do_queen_micro(queen, close_threats)
        # every now and then, check queen is not in the mineral field blocking workers
        elif self.bot.state.game_loop % 64 == 0:
            close_mfs: Units = self.bot.mineral_field.filter(
                lambda mf: mf.distance_to(townhall) < 8
            )
            # make a small adjustment away from the minerals
            if close_mfs and queen.distance_to(close_mfs.center) < 6:
                queen.move(queen.position.towards(close_mfs.center, -1))
