from sc2 import BotAI

from sc2_queens.policy import Policy


class Inject:
    def __init__(self, bot: BotAI, inject_policy: Policy):
        self.bot: BotAI = bot
        self.policy: Policy = inject_policy
        print(self.policy)
