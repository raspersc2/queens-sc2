from typing import Optional

from sc2 import BotAI
from sc2.unit import Unit
from sc2.units import Units
import numpy as np

from queens_sc2.queen_control.base_unit import BaseUnit
from queens_sc2.policy import NydusQueen, Policy


class Nydus(BaseUnit):
    def __init__(self, bot: BotAI, nydus_policy: Policy, map_data: Optional["MapData"]):
        super().__init__(bot, map_data)
        self.policy = nydus_policy

    async def handle_unit(
        self,
        air_threats_near_bases: Units,
        ground_threats_near_bases: Units,
        priority_enemy_units: Units,
        unit: Unit,
        th_tag: int = 0,
        grid: Optional[np.ndarray] = None,
    ) -> None:
        pass

    def update_policy(self, policy: Policy) -> None:
        self.policy = policy
