from sc2 import BotAI
from sc2.units import Units


class Creep:
    def __init__(self, bot: BotAI):
        self.bot: BotAI = bot

    async def spread_creep(self, queens: Units) -> None:
        pass

    async def spread_existing_tumors(self, tumors: Units):
        pass
