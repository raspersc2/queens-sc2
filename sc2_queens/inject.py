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

    async def handle_queen(self, queen: Unit, th_tag: int) -> None:
        print(self.enemy_ground_threats)
        ths: Units = self.bot.townhalls.ready.tags_in([th_tag])
        if ths:
            th: Unit = ths.first
            if self.policy.defend_against_air and self.enemy_air_threats:
                await self.do_queen_micro(queen, self.enemy_air_threats)
            elif self.policy.defend_against_air and self.enemy_ground_threats:
                await self.do_queen_micro(queen, self.enemy_ground_threats)
            else:
                abilities: List[AbilityId] = await self.bot.get_available_abilities(
                    queen
                )
                if AbilityId.EFFECT_INJECTLARVA in abilities:
                    queen(AbilityId.EFFECT_INJECTLARVA, th)
                # regardless of policy, chase away enemy close to th
                # but if queen gets too far away, walk back to th
                elif queen.distance_to(th) > 7:
                    queen.move(th.position)
                elif self.bot.enemy_units.closer_than(10, queen):
                    queen.attack(self.bot.enemy_units.closest_to(queen))
