from typing import Callable

from abc import ABC
from sc2.position import Point2


class Policy(ABC):
    def __init__(
        self,
        active: bool,
        max_queens: int,
        priority: bool,
        defend_against_air: bool,
        defend_against_ground: bool,
    ):
        self.active = active
        self.max_queens = max_queens
        self.priority = priority
        self.defend_against_air = defend_against_air
        self.defend_against_ground = defend_against_ground


class DefenceQueen(Policy):
    def __init__(self, rally_point: Point2, **kwargs):
        super().__init__(**kwargs)
        self.rally_point = rally_point


class CreepQueen(Policy):
    def __init__(
        self,
        distance_between_queen_tumors: int,
        distance_between_existing_tumors: int,
        should_tumors_block_expansions: bool,
        is_active: Callable,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.distance_between_queen_tumors = distance_between_queen_tumors
        self.distance_between_existing_tumors = distance_between_existing_tumors
        self.should_tumors_block_expansions = should_tumors_block_expansions
        self.is_active = is_active


class InjectQueen(Policy):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
