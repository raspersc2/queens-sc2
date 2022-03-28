from typing import List, Optional, Tuple, Union

from sc2.bot_ai import BotAI
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units
from scipy.spatial.ckdtree import cKDTree


class KDTrees:
    def __init__(self, bot: BotAI) -> None:
        self.bot: BotAI = bot
        self.empty_units: Units = Units([], bot)
        self.enemy_tree: Optional[cKDTree] = None
        self.own_tree: Optional[cKDTree] = None
        self.enemy_ground_tree: Optional[cKDTree] = None
        self.own_tree: Optional[cKDTree] = None
        self.enemy_flying_tree: Optional[cKDTree] = None

        self.enemy_flying: Units = self.empty_units
        self.enemy_ground: Units = self.empty_units

    def update(self) -> None:
        if all_enemy := self.bot.all_enemy_units:
            self.enemy_tree = self._create_tree(all_enemy)
            self.enemy_ground, self.enemy_flying = self._split_ground_fliers(all_enemy)
            if len(self.enemy_ground) > 0:
                self.enemy_ground_tree = self._create_tree(self.enemy_ground)
            else:
                self.enemy_ground_tree = None
            if len(self.enemy_flying) > 0:
                self.enemy_flying_tree = self._create_tree(self.enemy_flying)
            else:
                self.enemy_flying_tree = None
        else:
            self.enemy_tree, self.enemy_ground_tree, self.enemy_flying_tree = (
                None,
                None,
                None,
            )

        self.own_tree = self._create_tree(self.bot.units)

    @staticmethod
    def _create_tree(units: Union[Units, List[Unit]]):
        unit_position_list: List[List[float]] = [
            [unit.position.x, unit.position.y] for unit in units
        ]
        if unit_position_list:
            return cKDTree(unit_position_list)
        else:
            return None

    def _split_ground_fliers(self, units: Units) -> List[Units]:
        """
        Split units into ground units and flying units.
        Returns ground units, then flying units.
        @param units:
        @return: ground units, flying units
        """
        ground, fly = [], []
        for unit in units:
            if unit.is_flying:
                fly.append(unit)
            else:
                ground.append(unit)
        return [Units(ground, self.bot), Units(fly, self.bot)]

    def own_units_in_range_of_point(self, position: Point2, distance: float) -> Units:
        """
        Get all own units in range of the positions.
        @param position: the position or list of positions to get in range of
        @param distance: how far away to query
        """
        if self.own_tree is None:
            return self.empty_units

        in_range_list: List[Units] = []
        query_result = self.own_tree.query_ball_point([position], distance)
        for result in query_result:
            in_range_units = Units(
                [self.bot.units[index] for index in result], self.bot
            )
            in_range_list.append(in_range_units)
        return in_range_list[0]

    def enemy_units_in_range(
        self, units: Union[Units, List[Unit]], distance: float
    ) -> List[Units]:
        """
        Get all enemy units within distance of the positions.
        Use this to batch the query for a collection of units
        @param units: list of units we want to get enemies in range of
        @param distance: how far away to query
        """
        unit_positions: List[Point2] = [u.position for u in units]
        if self.enemy_tree is None:
            return [self.empty_units for _ in range(len(unit_positions))]

        in_range_list: List[Units] = []
        if unit_positions:
            query_result = self.enemy_tree.query_ball_point(unit_positions, distance)
            for result in query_result:
                in_range_units = Units(
                    [self.bot.all_enemy_units[index] for index in result], self.bot
                )
                in_range_list.append(in_range_units)
        return in_range_list

    def enemy_ground_in_range_of_point(
        self, position: Point2, distance: float
    ) -> Units:
        """
        Get all ground units in range of the position.
        Use this to query a single point
        @param position: the position or list of positions to get in range of
        @param distance: how far away to query
        """
        if self.enemy_ground_tree is None or not self.enemy_ground:
            return self.empty_units

        in_range_list: List[Units] = []
        query_result = self.enemy_ground_tree.query_ball_point([position], distance)
        for result in query_result:
            in_range_units = Units(
                [self.enemy_ground[index] for index in result], self.bot
            )
            in_range_list.append(in_range_units)
        return in_range_list[0]

    def enemy_flying_in_range_of_point(
        self, position: Point2, distance: float
    ) -> Units:
        """
        Get all air units in range of the position.
        Use this to query a single point
        @param position: the position or list of positions to get in range of
        @param distance: how far away to query
        """
        if self.enemy_flying_tree is None or not self.enemy_flying:
            return self.empty_units

        in_range_list: List[Units] = []
        query_result = self.enemy_flying_tree.query_ball_point([position], distance)
        for result in query_result:
            in_range_units = Units(
                [self.enemy_flying[index] for index in result], self.bot
            )
            in_range_list.append(in_range_units)
        return in_range_list[0]

    def enemy_units_in_range_of_point(self, position: Point2, distance: float) -> Units:
        """
        Get all units in range of the position.
        Use this to query a single point
        @param position: the position or list of positions to get in range of
        @param distance: how far away to query
        """
        if self.enemy_tree is None or not self.bot.all_enemy_units:
            return self.empty_units

        in_range_list: List[Units] = []
        query_result = self.enemy_tree.query_ball_point([position], distance)
        for result in query_result:
            in_range_units = Units(
                [self.bot.all_enemy_units[index] for index in result], self.bot
            )
            in_range_list.append(in_range_units)
        return in_range_list[0]

    def get_enemies_in_attack_range_of(
        self, unit: Unit, bonus_distance: int = 0.375
    ) -> Units:
        """Get all enemies in attack range of unit.
        WARNING: Wont be as accurate as `units.in_attack_range_of` since can't take into account enemy radius
        Bonus_distance has default of 0.375 (radius of a zergling)
        But this is way faster
        """
        if unit.air_range == unit.ground_range:
            return self.enemy_units_in_range(
                [unit], unit.air_range + unit.radius + bonus_distance
            )[unit.tag]
        if unit.can_attack_air:
            in_air_range = self.enemy_flying_in_range_of_point(
                unit.position, unit.air_range + unit.radius + bonus_distance
            )
        else:
            in_air_range = self.empty_units

        if unit.can_attack_ground:
            in_ground_range = self.enemy_ground_in_range_of_point(
                unit.position, unit.ground_range + unit.radius + bonus_distance
            )
        else:
            in_ground_range = self.empty_units
        return in_air_range + in_ground_range

    def get_ground_in_attack_range_of(
        self, unit: Unit, bonus_distance: int = 0.375
    ) -> Units:
        return self.enemy_ground_in_range_of_point(
            unit.position, unit.air_range + unit.radius + bonus_distance
        )

    def get_flying_in_attack_range_of(
        self, unit: Unit, bonus_distance: int = 0.375
    ) -> Units:
        return self.enemy_flying_in_range_of_point(
            unit.position, unit.air_range + unit.radius + bonus_distance
        )
