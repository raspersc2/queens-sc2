from typing import Optional

from sc2 import BotAI
from sc2.position import Point2
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.unit import Unit
from sc2.units import Units

from sc2_queens.base_unit import BaseUnit
from sc2_queens.policy import DefenceQueen


class Defence(BaseUnit):
    def __init__(self, bot: BotAI, defence_policy: DefenceQueen):
        super().__init__(bot)
        self.last_transfusion: float = 0.0
        self.policy: DefenceQueen = defence_policy

    def get_transfuse_target(self, from_pos: Point2) -> Optional[Unit]:
        transfuse_targets: Units = self.bot.units.filter(
            lambda unit: unit.health_percentage < 0.4
            and unit.type_id
            in {
                UnitID.BROODLORD,
                UnitID.CORRUPTOR,
                UnitID.HYDRALISK,
                UnitID.LURKER,
                UnitID.MUTALISK,
                UnitID.QUEEN,
                UnitID.RAVAGER,
                UnitID.ROACH,
                UnitID.SWARMHOSTMP,
                UnitID.ULTRALISK,
            }
        ) + self.bot.structures({UnitID.SPINECRAWLER, UnitID.SPORECRAWLER})

        if transfuse_targets and transfuse_targets.closer_than(10, from_pos):
            return transfuse_targets.closest_to(from_pos)

    async def handle_unit(self, unit: Unit) -> None:
        transfuse_target: Unit = self.get_transfuse_target(unit.position)
        if (
            transfuse_target
            and transfuse_target is not unit
            # and self.last_transfusion + 0.02 < self.bot.time
        ):
            unit(AbilityId.TRANSFUSION_TRANSFUSION, transfuse_target)
            self.last_transfusion = self.bot.time
        elif self.policy.defend_against_ground and self.enemy_ground_threats:
            await self.do_queen_micro(unit, self.enemy_ground_threats)
        elif self.policy.defend_against_air and self.enemy_air_threats:
            await self.do_queen_micro(unit, self.enemy_air_threats)
        elif self.policy.attack_condition():
            unit.attack(self.policy.attack_target)
        elif unit.distance_to(self.policy.rally_point) > 7 and len(unit.orders) == 0:
            unit.move(self.policy.rally_point)

    def update_policy(self, policy) -> None:
        self.policy = policy
