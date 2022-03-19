from typing import List, Optional, Set
import numpy as np

from sc2.bot_ai import BotAI
from sc2.ids.ability_id import AbilityId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from queens_sc2.kd_trees import KDTrees
from queens_sc2.queen_control.base_unit import BaseUnit
from queens_sc2.policy import Policy


class CreepDropperlord(BaseUnit):
    creep_map: np.ndarray
    # allow queen time to get the order to plant a tumor
    LOCK_OL_LOADING_FOR: float = 3.5

    def __init__(
        self,
        bot: BotAI,
        kd_trees: KDTrees,
        creep_dropperlord_policy: Policy,
        map_data: Optional["MapData"],
    ):
        super().__init__(bot, kd_trees, map_data)
        self.policy = creep_dropperlord_policy
        self.dropperlord_tag: int = 0
        self.creep_targets: List[Point2] = []
        self.creep_target_index: int = -1
        self.current_creep_target: Point2 = self.bot.start_location
        self.first_iteration: bool = True
        self.unloaded_at: float = 0.0

    async def handle_queen_dropperlord(
        self,
        creep_map: np.ndarray,
        queen_tag: int,
        queens: Units,
        air_grid: Optional[np.ndarray] = None,
        avoidance_grid: Optional[np.ndarray] = None,
        grid: Optional[np.ndarray] = None,
        creep_queen_dropperlord_tags: Optional[Set[int]] = None,
    ) -> None:
        self.creep_map = creep_map
        queen: Optional[Unit] = None
        dropperlord_queens: Units = queens.tags_in([queen_tag])
        if dropperlord_queens:
            queen = dropperlord_queens.first

        if self.map_data and not self.is_position_safe(grid, self.current_creep_target):
            self._find_new_creep_target(air_grid, grid)

        self.creep_targets = self.policy.target_expansions
        if len(self.creep_targets) == 0:
            return

        # need an initial target
        if self.first_iteration:
            self._find_new_creep_target(air_grid, grid)
            self.first_iteration = False

        keep_queen_safe: bool = False
        if queen and await self.keep_queen_safe(avoidance_grid, grid, queen):
            keep_queen_safe = True

        if len(creep_queen_dropperlord_tags) > 0:
            ready_dropperlords: Units = self.bot.units.filter(
                lambda u: u.tag in creep_queen_dropperlord_tags
            )
            if ready_dropperlords:
                await self._manage_queen_dropperlord(
                    ready_dropperlords.first, air_grid, grid, queen
                )

            if queen and not keep_queen_safe:
                await self._manage_dropperlord_queen(
                    ready_dropperlords, air_grid, grid, queen
                )

    async def handle_unit(
        self,
        air_threats_near_bases: Units,
        ground_threats_near_bases: Units,
        priority_enemy_units: Units,
        unit: Unit,
        th_tag: int = 0,
        avoidance_grid: Optional[np.ndarray] = None,
        grid: Optional[np.ndarray] = None,
        nydus_networks: Optional[Units] = None,
        nydus_canals: Optional[Units] = None,
        natural_position: Optional[Point2] = None,
    ) -> None:
        pass

    def update_policy(self, policy: Policy) -> None:
        self.policy = policy

    async def _manage_dropperlord_queen(
        self,
        dropperlords: Optional[Units],
        air_grid: np.ndarray,
        grid: np.ndarray,
        queen: Unit,
    ) -> None:
        dropperlord: Unit = dropperlords.first if dropperlords else None
        if dropperlord and queen.tag in dropperlord.passengers_tags:
            return

        if queen.distance_to(self.current_creep_target) < 15:
            if queen.energy >= 25 and self.bot.has_creep(self.current_creep_target):
                queen(AbilityId.BUILD_CREEPTUMOR_QUEEN, self.current_creep_target)
                self._find_new_creep_target(air_grid, grid)
                return
            else:
                await self.move_towards_safe_spot(queen, grid)
        # not near target and there is a dropperlord, go find it
        elif (
            dropperlord
            and dropperlord.is_ready
            and dropperlord.health_percentage > 0.2
            and self.bot.time > self.unloaded_at + self.LOCK_OL_LOADING_FOR
        ):
            # if queen.distance_to(dropperlord) < 10:
            #     queen(AbilityId.SMART, dropperlord)
            # else:
            move_to: Point2 = dropperlord.position
            if self.map_data:
                path: List[Point2] = self.map_data.pathfind(
                    queen.position, dropperlord.position, grid, sensitivity=5
                )
                if path and len(path) > 0:
                    move_to: Point2 = path[0]
            queen.move(move_to)
        # no dropperlord right now
        elif not dropperlord:
            await self.move_towards_safe_spot(queen, grid)

    async def _manage_queen_dropperlord(
        self,
        dropperlord: Optional[Unit],
        air_grid: np.ndarray,
        grid: np.ndarray,
        queen: Optional[Unit],
    ) -> None:
        if not dropperlord:
            return
        if (
            not dropperlord.is_using_ability(AbilityId.BEHAVIOR_GENERATECREEPON)
            and dropperlord.cargo_used == 0
        ):
            dropperlord(AbilityId.BEHAVIOR_GENERATECREEPON)

        if dropperlord.health_percentage < 0.2:
            dropperlord(AbilityId.UNLOADALLAT_OVERLORD, dropperlord.position)
            self.dropperlord_tag = 0
            return

        # move dropperlord to queen if she is not inside right now
        if dropperlord.cargo_used == 0:
            await self._move_dropperlord_to_queen(dropperlord, air_grid, queen)
        # queen in dropperlord, move to a target
        else:
            if (
                self.bot.distance_math_hypot_squared(
                    dropperlord.position, self.current_creep_target
                )
                > 25
            ):
                if self._current_area_has_no_creep(grid, dropperlord.position):
                    self.current_creep_target = dropperlord.position
                    return
                if self.map_data:
                    path: List[Point2] = self.map_data.pathfind(
                        dropperlord.position,
                        self.current_creep_target,
                        air_grid,
                        sensitivity=2,
                    )
                    if path and len(path) > 0:
                        move_to: Point2 = path[0]
                    else:
                        move_to: Point2 = self.current_creep_target
                    dropperlord.move(move_to)
                else:
                    dropperlord.move(self.current_creep_target)
            else:
                dropperlord(AbilityId.UNLOADALLAT_OVERLORD, self.current_creep_target)
                self.unloaded_at = self.bot.time

    async def _move_dropperlord_to_queen(
        self, dropperlord: Unit, grid: Optional[np.ndarray], queen: Optional[Unit]
    ) -> None:
        if not queen:
            return

        move_to: Point2 = queen.position
        if (
            dropperlord.is_ready
            and len(dropperlord.passengers) == 0
            # and not queen.is_using_ability(AbilityId.BUILD_CREEPTUMOR_QUEEN)
        ):
            if (
                self.bot.distance_math_hypot_squared(
                    dropperlord.position, queen.position
                )
                > 100.0
            ):
                if self.map_data:
                    path: List[Point2] = self.map_data.pathfind(
                        dropperlord.position, queen.position, grid, sensitivity=5
                    )
                    if path and len(path) > 0:
                        move_to: Point2 = path[0]

                dropperlord.move(move_to)
            elif self.bot.time > self.unloaded_at + self.LOCK_OL_LOADING_FOR:
                dropperlord(AbilityId.LOAD_OVERLORD, queen)

    def _find_new_creep_target(self, air_grid: np.ndarray, grid: np.ndarray):
        """
        target_area should be an expansion location we want to creep
        However, we don't want to block the target for ourselves
        """
        # prevent rare crash
        if len(self.creep_targets) == 0:
            return self.bot.game_info.map_center

        self.creep_target_index += 1
        if self.creep_target_index >= len(self.creep_targets):
            self.creep_target_index = 0

        target_area: Point2 = self.creep_targets[self.creep_target_index]
        for i in range(50):
            random_target: Point2 = self.get_random_position_from(
                from_position=target_area, distance=8
            )
            if (
                self.map_data
                and not self.is_position_safe(grid, random_target)
                and not self.is_position_safe(air_grid, random_target)
            ):
                continue
            if self.bot.get_terrain_z_height(
                random_target
            ) == self.bot.get_terrain_z_height(
                target_area
            ) and self.bot.in_pathing_grid(
                random_target
            ):
                self.current_creep_target = random_target
                return

        # in case we found nothing at all
        return self.bot.game_info.map_center

    def _current_area_has_no_creep(self, grid: np.ndarray, position: Point2) -> bool:
        if (
            self.bot.in_pathing_grid(position)
            and not self.bot.has_creep(position)
            and not self.position_blocks_expansion(position)
        ):
            if self.map_data and not self.is_position_safe(grid, position):
                return False
            # if there is no creep nearby, then we determine there is no creep in this area
            closest_creep_tile: Point2 = self._find_closest_to_target(
                position, self.creep_map
            )
            if closest_creep_tile.distance_to(position) > 12:
                return True

        return False
