import random
from typing import Dict, Optional

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
            "creep_queens": {"active": True, "priority": True, "max": 4},
            "inject_queens": {"active": True, "priority": False, "max": 1},
        }
        self.queens = Queens(self, debug=True, **queen_policy)
        self.client.game_step = 8

    async def on_step(self, iteration: int) -> None:

        # call the queen library to handle our queens
        # can optionally pass in a custom selection of queens, ie:
        # queens: Units = self.units(UnitID.QUEEN).tags_in(self.sc2_queen_tags)
        await self.queens.manage_queens(iteration)
        # can repurpose queens by passing a new policy
        if iteration == 3000:
            # turn every queen into defence queen
            queen_policy: Dict = {
                "creep_queens": {"active": True, "max": 1},
                "defence_queens": {
                    "active": True,
                    "attack_condition": lambda: self.units(UnitID.QUEEN).amount > 50,
                },
                "inject_queens": {"active": False, "max": 0},
            }
            self.queens.set_new_policy(reset_roles=True, **queen_policy)

        # basic bot that only builds queens
        await self.do_basic_zergbot(iteration)

    async def on_unit_destroyed(self, unit_tag: int):
        # checks if unit is a queen or th, lib then handles appropriately
        self.queens.remove_unit(unit_tag)

    @property
    def need_overlord(self) -> bool:
        return not self.already_pending(UnitID.OVERLORD) and self.supply_left <= 3

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
            if self.need_overlord and self.can_afford(UnitID.OVERLORD):
                self.larva.first.train(UnitID.OVERLORD)
            # build workers
            if self.supply_workers <= 40 and self.can_afford(UnitID.DRONE):
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
        if self.can_afford(UnitID.HATCHERY) and not self.already_pending(
            UnitID.HATCHERY
        ):
            await self.expand_now(max_distance=0)

        # spines/spores if minerals too high
        if self.minerals > 400 and self.structures(UnitID.SPAWNINGPOOL).ready:
            structure: UnitID = random.choice(
                [UnitID.SPINECRAWLER, UnitID.SPORECRAWLER]
            )
            # we are dumb, pick random pos on map
            x = random.choice(range(0, self.game_info.map_size.width))
            y = random.choice(range(0, self.game_info.map_size.height))
            # let sc2 library do the magic of finding a placement from random pos
            pos: Point2 = await self.find_placement(structure, Point2((x, y)))
            if pos and not self.queens.creep._position_blocks_expansion(pos):
                worker: Unit = self.select_worker(pos)
                worker.build(structure, pos)

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
random_map = random.choice(["EverDreamLE"])
random_race = random.choice([Race.Zerg, Race.Terran, Race.Protoss])
bot = Bot(Race.Zerg, ZergBot())
run_game(
    maps.get(random_map),
    [bot, Computer(Race.Terran, Difficulty.Hard)],
    realtime=False,
    save_replay_as="ZvTElite.SC2Replay",
)
