from sc2 import BotAI
from sc2.ids.ability_id import AbilityId
from sc2.unit import Unit

from queens_sc2.base_unit import BaseUnit
from queens_sc2.policy import Policy


class Defence(BaseUnit):
    def __init__(self, bot: BotAI, defence_policy: Policy):
        super().__init__(bot)
        self.last_transfusion: float = 0.0
        self.policy: Policy = defence_policy
        self.used_transfuse_this_step: bool = False

    async def handle_unit(self, unit: Unit) -> None:
        transfuse_target: Unit = self.get_transfuse_target(unit.position)
        self.used_transfuse_this_step: bool = False
        if (
            transfuse_target
            and transfuse_target is not unit
            and not self.used_transfuse_this_step
        ):
            unit(AbilityId.TRANSFUSION_TRANSFUSION, transfuse_target)
            self.used_transfuse_this_step = True
        elif self.policy.attack_condition():
            await self.do_queen_offensive_micro(unit, self.policy.attack_target)
        elif self.policy.defend_against_ground and self.enemy_ground_threats:
            await self.do_queen_micro(unit, self.enemy_ground_threats)
        elif self.policy.defend_against_air and self.enemy_air_threats:
            await self.do_queen_micro(unit, self.enemy_air_threats)
        elif unit.distance_to(self.policy.rally_point) > 12:
            unit.move(self.policy.rally_point)

    def update_policy(self, policy: Policy) -> None:
        self.policy = policy
