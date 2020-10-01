from typing import List
from sc2 import BotAI
from sc2.ids.ability_id import AbilityId
from sc2.unit import Unit
from sc2.units import Units

from sc2_queens.base_unit import BaseUnit
from sc2_queens.policy import Policy


class Inject(BaseUnit):
    def __init__(self, bot: BotAI, inject_policy: Policy):
        super().__init__(bot)
        self.policy: Policy = inject_policy

    async def handle_unit(self, unit: Unit, th_tag: int) -> None:
        ths: Units = self.bot.townhalls.ready.tags_in([th_tag])
        if ths:
            th: Unit = ths.first
            if self.policy.defend_against_air and self.enemy_air_threats:
                await self.do_queen_micro(unit, self.enemy_air_threats)
            elif self.policy.defend_against_ground and self.enemy_ground_threats:
                await self.do_queen_micro(unit, self.enemy_ground_threats)
            else:
                abilities: List[AbilityId] = await self.bot.get_available_abilities(
                    unit
                )
                if AbilityId.EFFECT_INJECTLARVA in abilities:
                    unit(AbilityId.EFFECT_INJECTLARVA, th)
                # regardless of policy, chase away enemy close to th
                # but if queen gets too far away, walk back to th
                elif unit.distance_to(th) > 7:
                    unit.move(th.position)
                elif self.bot.enemy_units.closer_than(10, unit):
                    unit.attack(self.bot.enemy_units.closest_to(unit))

    def update_policy(self, policy) -> None:
        self.policy = policy
