from typing import Dict, Optional
import random
from sc2 import BotAI, Difficulty, Race, maps, run_game
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.player import Bot, Computer
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from sc2_queens.queens import Queens


class ZergBot(BotAI):
    """
    Example ZergBot, expands and then only builds queens
    Demonstrates the sc2-queens lib in action
    """

    queens: Queens

    async def on_start(self):
        # override defaults in the sc2_queens lib by passing a policy:
        queen_policy: Dict = {
            "creep_queens": {"active": True, "max": 2},
            "defence_queens": {"max": 100},
            "inject_queens": {"max": 6},
        }
        self.queens = Queens(self, debug=True, **queen_policy)

    async def on_step(self, iteration: int) -> None:

        # call the queen library to handle our queens
        # can optionally pass in a custom selection of queens, ie:
        # queens: Units = self.units(UnitID.QUEEN).tags_in(self.sc2_queen_tags)
        await self.queens.manage_queens()

        # basic bot that only builds queens
        await self.do_basic_zergbot(iteration)

    async def on_unit_destroyed(self, unit_tag: int):
        # checks if unit is a queen or th, lib then handles appropriately
        self.queens.remove_unit(unit_tag)

    @property
    def need_overlord(self) -> bool:
        return not self.already_pending(UnitID.OVERLORD) and self.supply_left <= 1

    async def do_basic_zergbot(self, iteration: int) -> None:
        if iteration % 16 == 0:
            await self.distribute_workers()

        # queen production
        if (
            self.structures(UnitID.SPAWNINGPOOL).ready
            and self.can_afford(UnitID.QUEEN)
            and self.townhalls.idle
        ):
            self.townhalls.idle.first.train(UnitID.QUEEN)

        # drones and overlords from larva
        if self.larva:
            # overlords
            if self.need_overlord:
                self.larva.first.train(UnitID.OVERLORD)
            # build up to 20 workers
            if self.supply_workers <= 20 and self.can_afford(UnitID.DRONE):
                self.larva.first.train(UnitID.DRONE)

        # spawning pool
        if not (
            self.structures(UnitID.SPAWNINGPOOL)
            or self.already_pending(UnitID.SPAWNINGPOOL)
        ) and self.can_afford(UnitID.SPAWNINGPOOL):
            pos: Point2 = await self.find_placement(
                UnitID.SPAWNINGPOOL, self.main_base_ramp.top_center
            )
            worker: Unit = self.select_worker(pos)
            if worker:
                worker.build(UnitID.SPAWNINGPOOL, pos)

        # expand
        if not self.already_pending(UnitID.HATCHERY) and self.can_afford(
            UnitID.HATCHERY
        ):
            await self.expand_now(max_distance=0)

    def select_worker(self, target: Point2) -> Optional[Unit]:
        workers: Units = self.workers.filter(
            lambda unit: not unit.is_carrying_minerals and unit.is_collecting
        )
        return (
            workers.closest_to(target)
            if workers
            else (self.workers.first if self.workers else None)
        )


# Local game
random_map = random.choice(["EverDreamLE",])
random_race = random.choice([Race.Zerg, Race.Terran, Race.Protoss])
bot = Bot(Race.Zerg, ZergBot())
run_game(
    maps.get(random_map),
    [bot, Computer(random_race, Difficulty.Easy),],
    realtime=False,
)
