import random
from typing import Dict, Optional, List

from sc2 import BotAI, Difficulty, Race, maps, run_game
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.player import Bot, Computer
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units
from queens_sc2.queens import Queens


class ZergBot(BotAI):
    """
    Example ZergBot, expands and then only builds queen_control
    Demonstrates the sc2-queen_control lib in action
    """

    mid_game_queen_policy: Dict
    early_game_queen_policy: Dict
    natural_pos: Point2
    queens: Queens

    def __init__(self) -> None:
        super().__init__()
        # SET TO FALSE BEFORE UPLOADING TO LADDER!
        self.debug: bool = True
        self.basic_bo: List[UnitID] = [
            UnitID.OVERLORD,
            UnitID.DRONE,
            UnitID.DRONE,
            UnitID.HATCHERY,
            UnitID.DRONE,
            UnitID.DRONE,
            UnitID.SPAWNINGPOOL,
            UnitID.DRONE,
            UnitID.DRONE,
            UnitID.DRONE,
            UnitID.OVERLORD,
        ]
        self.bo_step: int = 0
        self.natural_drone_tag: int = 0
        self.switched_queen_policy: bool = False

    async def on_before_start(self) -> None:
        self.larva.first.train(UnitID.DRONE)
        for drone in self.workers:
            closest_patch: Unit = self.mineral_field.closest_to(drone)
            drone.gather(closest_patch)

    async def on_start(self) -> None:
        self.client.raw_affects_selection = True
        self.natural_pos = await self._find_natural()
        self.early_game_queen_policy = {
            "creep_queens": {
                "active": True,
                "priority": 2,
                "max": 4,
                "defend_against_ground": True,
                "first_tumor_position": self.start_location.towards(
                    self.main_base_ramp.top_center, 5
                ),
                "priority_defence_list": {
                    UnitID.BATTLECRUISER,
                    UnitID.LIBERATOR,
                    UnitID.LIBERATORAG,
                    UnitID.VOIDRAY,
                },
            },
            "defence_queens": {
                "priority_defence_list": {
                    UnitID.BATTLECRUISER,
                    UnitID.LIBERATOR,
                    UnitID.LIBERATORAG,
                    UnitID.VOIDRAY,
                }
            },
            "inject_queens": {
                "active": True,
                "priority": False,
                "max": 2,
                "priority_defence_list": {
                    UnitID.BATTLECRUISER,
                    UnitID.LIBERATOR,
                    UnitID.LIBERATORAG,
                    UnitID.VOIDRAY,
                },
            },
        }
        self.mid_game_queen_policy = {
            "creep_queens": {
                "max": 2,
                "priority": True,
                "distance_between_existing_tumors": 4,
                "defend_against_ground": False,
                "spread_style": "random",
            },
            "defence_queens": {
                "attack_condition": lambda: self.units(UnitID.QUEEN).amount > 20,
            },
            "inject_queens": {"active": False, "max": 0},
        }
        # override defaults in the queens_sc2 lib by passing a policy:
        self.queens = Queens(
            self, debug=self.debug, queen_policy=self.early_game_queen_policy
        )

    async def on_unit_destroyed(self, unit_tag: int):
        # checks if unit is a queen or th, lib then handles appropriately
        self.queens.remove_unit(unit_tag)

    async def on_step(self, iteration: int) -> None:
        # call the queen library to handle our queen_control
        # can optionally pass in a custom selection of queen_control, ie:
        # queen_control: Units = self.units(UnitID.QUEEN).tags_in(self.sc2_queen_tags)
        await self.queens.manage_queens(iteration)
        # can repurpose queen_control by passing a new policy
        if not self.switched_queen_policy and self.time > 480:
            # adjust queen policy, allow stuck tumors to escape
            self.queens.set_new_policy(self.mid_game_queen_policy)
            self.switched_queen_policy = True

        # can update creep targets
        # if iteration == 10:
        #     self.queen_control.update_creep_targets([self.enemy_start_locations[0]])

        # basic bot that only builds queen_control
        await self.do_basic_zergbot(iteration)

    @property
    def need_overlord(self) -> bool:
        if self.supply_cap < 200:
            # supply blocked / overlord killed, ok to get extra overlords
            if (
                self.supply_left <= 0
                and self.supply_used >= 28
                and self.already_pending(UnitID.OVERLORD)
                < (self.townhalls.ready.amount + 1)
            ):
                return True
            # just one at a time at low supply counts
            elif (
                40 > self.supply_used >= 13
                and self.supply_left < 3
                and self.already_pending(UnitID.OVERLORD) < 1
            ):
                return True
            # overlord production scales up depending on bases taken
            elif self.supply_left < 3 * self.townhalls.amount and self.already_pending(
                UnitID.OVERLORD
            ) < (self.townhalls.ready.amount - 1):
                return True
        return False

    async def do_basic_zergbot(self, iteration: int) -> None:
        if iteration % 16 == 0:
            await self.distribute_workers()

        self.adjust_attack_target()

        if self.bo_step < len(self.basic_bo):
            await self.do_build_order()
        else:
            # queen production
            if (
                self.structures(UnitID.SPAWNINGPOOL).ready
                and self.can_afford(UnitID.QUEEN)
                and self.townhalls.idle
            ):
                self.townhalls.idle.first.train(UnitID.QUEEN)

            # drones and overlords from larva
            if self.larva:
                num_workers: int = int(
                    self.workers.amount + self.already_pending(UnitID.DRONE)
                )
                # overlords
                if self.need_overlord and self.can_afford(UnitID.OVERLORD):
                    self.larva.first.train(UnitID.OVERLORD)
                # build workers
                if num_workers <= 60 and self.can_afford(UnitID.DRONE):
                    self.larva.first.train(UnitID.DRONE)

            # ensure there is a spawning pool
            if not (
                self.structures(UnitID.SPAWNINGPOOL)
                or self.already_pending(UnitID.SPAWNINGPOOL)
            ) and self.can_afford(UnitID.SPAWNINGPOOL):
                await self._build_pool()

            # expand
            if self.can_afford(UnitID.HATCHERY) and self.time > 160:
                await self.expand_now(max_distance=0)

    def adjust_attack_target(self) -> None:
        enemy_units: Units = self.enemy_units.filter(
            lambda u: u.type_id
            not in {
                UnitID.SCV,
                UnitID.DRONE,
                UnitID.PROBE,
                UnitID.MULE,
                UnitID.LARVA,
                UnitID.EGG,
                UnitID.CHANGELING,
                UnitID.CHANGELINGZERGLING,
                UnitID.CHANGELINGZERGLINGWINGS,
                UnitID.REAPER,
            }
            and not u.is_flying
        )
        enemy_structures: Units = self.enemy_structures
        if enemy_units:
            self.queens.update_attack_target(
                enemy_units.closest_to(self.start_location).position
            )
        elif enemy_structures:
            self.queens.update_attack_target(
                enemy_structures.closest_to(self.start_location).position
            )
        else:
            self.queens.update_attack_target(self.enemy_start_locations[0])

    async def do_build_order(self) -> None:
        current_step: UnitID = self.basic_bo[self.bo_step]
        if (
            current_step in (UnitID.DRONE, UnitID.OVERLORD)
            and self.larva
            and self.can_afford(current_step)
        ):
            self.larva.first.train(current_step)
            self.bo_step += 1
        elif current_step == UnitID.HATCHERY and self.minerals > 185 and self.workers:
            if self.natural_drone_tag == 0:
                worker: Unit = self._select_worker(self.natural_pos)
                if worker:
                    self.natural_drone_tag = worker.tag
                    worker.move(self.natural_pos)
            elif self.can_afford(UnitID.HATCHERY):
                workers: Units = self.workers.tags_in([self.natural_drone_tag])
                if workers:
                    workers.first.build(UnitID.HATCHERY, self.natural_pos)
                    self.bo_step += 1
                # worker is missing, fall back option
                else:
                    await self.expand_now(max_distance=0)
                    self.bo_step += 1

        elif (
            current_step == UnitID.SPAWNINGPOOL
            and self.can_afford(UnitID.SPAWNINGPOOL)
            and self.workers
        ):
            await self._build_pool()
            self.bo_step += 1
        elif current_step == UnitID.QUEEN and self.can_afford(current_step):
            self.townhalls.first.train(current_step)
            self.bo_step += 1

    async def _build_pool(self) -> None:
        pos: Point2 = await self.find_placement(
            UnitID.SPAWNINGPOOL,
            self.start_location.towards(self.main_base_ramp.top_center, 3),
        )
        worker: Unit = self._select_worker(pos)
        if worker:
            worker.build(UnitID.SPAWNINGPOOL, pos)

    async def _find_natural(self) -> Point2:
        min_distance: float = 9999.0
        pos: Point2 = Point2((0, 0))
        for el in self.expansion_locations_list:
            if self.start_location.distance_to(el) < self.EXPANSION_GAP_THRESHOLD:
                continue

            distance = await self.client.query_pathing(self.start_location, el)
            if distance:
                if distance < min_distance:
                    min_distance = distance
                    pos = el

        return pos

    def _select_worker(self, target: Point2) -> Optional[Unit]:
        workers: Units = self.workers.filter(
            lambda unit: not unit.is_carrying_minerals and unit.is_collecting
        )
        return (
            workers.closest_to(target)
            if workers
            else (self.workers.first if self.workers else None)
        )


if __name__ == "__main__":
    # Local game
    random_map = random.choice(["EverDreamLE"])
    random_race = random.choice([Race.Zerg, Race.Terran, Race.Protoss])
    bot = Bot(Race.Zerg, ZergBot())
    run_game(
        maps.get(random_map),
        [bot, Computer(Race.Terran, Difficulty.Hard)],
        realtime=False,
        # save_replay_as="ZvTElite.SC2Replay",
    )
