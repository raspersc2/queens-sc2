from typing import List, Optional
from sc2 import BotAI
from sc2.position import Point2
from sc2.units import Units
from scipy.spatial.ckdtree import cKDTree


class KDTrees:
    def __init__(self, bot: BotAI) -> None:
        self.bot: BotAI = bot
        self.enemy_tree: Optional[cKDTree] = None
        self.own_tree: Optional[cKDTree] = None
        self.empty_units: Units = Units([], self.bot)

    def update(self) -> None:
        self.enemy_tree = self._create_tree(self.bot.all_enemy_units)
        self.own_tree = self._create_tree(self.bot.units)

    @staticmethod
    def _create_tree(units: Units):
        unit_position_list: List[List[float]] = [
            [unit.position.x, unit.position.y] for unit in units
        ]
        if unit_position_list:
            return cKDTree(unit_position_list)
        else:
            return None

    def own_units_in_range(self, position: Point2, distance: float) -> Units:
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

    def enemy_units_in_range(self, position: Point2, distance: float) -> Units:
        """
        Get all own units in range of the positions.
        @param position: the position or list of positions to get in range of
        @param distance: how far away to query
        """
        if self.enemy_tree is None:
            return self.empty_units

        in_range_list: List[Units] = []
        query_result = self.enemy_tree.query_ball_point([position], distance)
        for result in query_result:
            in_range_units = Units(
                [self.bot.all_enemy_units[index] for index in result], self.bot
            )
            in_range_list.append(in_range_units)
        return in_range_list[0]
