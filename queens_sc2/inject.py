from sc2 import BotAI
from sc2.ids.ability_id import AbilityId
from sc2.unit import Unit
from sc2.units import Units

from queens_sc2.base_unit import BaseUnit
from queens_sc2.policy import Policy


class Inject(BaseUnit):
    def __init__(self, bot: BotAI, inject_policy: Policy):
        super().__init__(bot)
        self.policy = inject_policy

    async def handle_unit(
        self,
        air_threats_near_bases: Units,
        ground_threats_near_bases: Units,
        unit: Unit,
        th_tag: int,
    ) -> None:
        if self.policy.pass_own_threats:
            air_threats: Units = air_threats_near_bases
            ground_threats: Units = ground_threats_near_bases
        else:
            air_threats: Units = self.enemy_air_threats
            ground_threats: Units = self.enemy_ground_threats

        ths: Units = self.bot.townhalls.ready.tags_in([th_tag])
        if ths:
            th: Unit = ths.first
            if self.priority_enemy_units:
                await self.do_queen_micro(unit, self.priority_enemy_units)
            elif self.policy.defend_against_air and air_threats:
                await self.do_queen_micro(unit, air_threats)
            elif self.policy.defend_against_ground and ground_threats:
                await self.do_queen_micro(unit, ground_threats)
            else:
                if unit.energy >= 25:
                    unit(AbilityId.EFFECT_INJECTLARVA, th)
                # regardless of policy, chase away enemy close to th
                # but if queen gets too far away, walk back to th
                elif unit.distance_to(th) > 7:
                    unit.move(th.position)
                elif self.bot.enemy_units.filter(
                    lambda enemy: enemy.position.distance_to(unit) < 10
                ):
                    unit.attack(self.find_closest_enemy(unit, self.bot.enemy_units))
                    
    def update_policy(self, policy: Policy) -> None:
        self.policy = policy
