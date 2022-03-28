from typing import Dict

# avoid circular import
import queens_sc2.sharpy as sharpy
from sharpy.plans.acts import ActBase


class SetQueensSc2Policy(ActBase):
    """
    Allows you to set a queen policy as part of your build order.
    """

    def __init__(self, queen_policy: Dict, policy_name: str = None):
        super().__init__()
        self.queen_policy = queen_policy
        self.policy_name = policy_name
        self.done = False

    async def execute(self) -> bool:
        if not self.done:
            self.knowledge.get_manager(sharpy.QueensSc2Manager).set_new_policy(
                self.queen_policy
            )
            self.print(f"Queens policy has changed.")
            if self.policy_name:
                self.print(f"New policy: {self.policy_name}")
            self.done = True
        return True
