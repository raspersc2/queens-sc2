import random
from typing import Dict

from sc2 import BotAI, Race, maps, run_game
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.player import Bot
from sc2.position import Point2
from sc2.unit import Unit
from queens_sc2.consts import QueenRoles
from queens_sc2.queens import Queens

from MapAnalyzer import MapData


class ZergBot(BotAI):
    """
    Example ZergBot, expands and then only builds queen_control
    Demonstrates the sc2-queen_control lib in action
    """

    queen_policy: Dict
    natural_pos: Point2
    queens: Queens
    map_data: MapData

    def __init__(self) -> None:
        super().__init__()
        self.debug: bool = True

    async def on_before_start(self) -> None:
        self.larva.first.train(UnitID.DRONE)
        for drone in self.workers:
            closest_patch: Unit = self.mineral_field.closest_to(drone)
            drone.gather(closest_patch)

    async def on_start(self) -> None:
        self.map_data = MapData(self)
        self.queen_policy = {
            "creep_queens": {
                "active": False,
            },
            "defence_queens": {"active": True},
            "inject_queens": {
                "active": False,
            },
            "nydus_queens": {
                "nydus_target": self.game_info.map_center,
                "steal_from": {QueenRoles.Defence},
            },
        }
        # override defaults in the queens_sc2 lib by passing a policy:
        self.queens = Queens(
            self,
            debug=self.debug,
            queen_policy=self.queen_policy,
            map_data=self.map_data,
        )
        # debug spawn everything we need to test nydus queen_control
        await self._setup_nydus_scenario()

    async def on_unit_destroyed(self, unit_tag: int):
        # checks if unit is a queen or th, lib then handles appropriately
        self.queens.remove_unit(unit_tag)

    async def on_step(self, iteration: int) -> None:
        # call the queen library to handle our queen_control
        await self.queens.manage_queens(iteration)

        # some rudimentary chat debug, made for a specific scenario
        messages = self.state.chat
        if len(messages) > 0:
            chat = messages[0].message.upper()
            commands = chat.split()
            first_command = commands[0]

            if first_command == "MAKE_CANAL":
                await self.client.debug_create_unit(
                    [[UnitID.NYDUSCANAL, 1, self.game_info.map_center, 1]]
                )

            if first_command == "KILL_CANAL":
                must_die = self.structures(UnitID.NYDUSCANAL)
                if must_die:
                    await self.client.debug_kill_unit(must_die.tags)

            if first_command == "ENEMY_1":
                await self.client.debug_create_unit(
                    [[UnitID.MARINE, 5, self.game_info.map_center, 2]]
                )

    async def _setup_nydus_scenario(self) -> None:
        await self.client.debug_create_unit(
            [
                [
                    UnitID.NYDUSNETWORK,
                    1,
                    self.start_location.towards(self.main_base_ramp.top_center, 10),
                    1,
                ]
            ]
        )
        await self.client.debug_create_unit([[UnitID.QUEEN, 5, self.start_location, 1]])


class BlankBot(BotAI):
    async def on_step(self, iteration) -> None:
        pass


if __name__ == "__main__":
    # Local game
    random_map = random.choice(["SubmarineLE"])
    bot = Bot(Race.Zerg, ZergBot())
    blank_bot = Bot(Race.Terran, BlankBot())
    run_game(
        maps.get(random_map),
        [bot, blank_bot],
        realtime=False,
        # save_replay_as="ZvTElite.SC2Replay",
    )
