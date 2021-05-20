from abc import ABC
from typing import Callable, List, Set

from sc2.position import Point2
from sc2.ids.unit_typeid import UnitTypeId as UnitID


class Policy(ABC):
    def __init__(
        self,
        active: bool,
        max_queens: int,
        priority: bool,
        defend_against_air: bool,
        defend_against_ground: bool,
        pass_own_threats: bool,
        priority_defence_list: Set[UnitID],
    ):
        self.active = active
        self.max_queens = max_queens
        self.priority = priority
        self.defend_against_air = defend_against_air
        self.defend_against_ground = defend_against_ground
        self.pass_own_threats = pass_own_threats
        self.priority_defence_list = priority_defence_list


class DefenceQueen(Policy):
    def __init__(
        self,
        attack_condition: Callable,
        attack_target: Point2,
        rally_point: Point2,
        should_nydus: bool,
        max_nydus_queens: int,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.attack_condition = attack_condition
        self.attack_target = attack_target
        self.rally_point = rally_point
        self.should_nydus = should_nydus
        self.max_nydus_queens = max_nydus_queens


class CreepQueen(Policy):
    def __init__(
        self,
        distance_between_existing_tumors: int,
        distance_between_queen_tumors: int,
        min_distance_between_existing_tumors: int,
        should_tumors_block_expansions: bool,
        creep_targets: List[Point2],
        spread_style: str,
        rally_point: Point2,
        target_perc_coverage: float,
        first_tumor_position: Point2,
        prioritize_creep: Callable,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.distance_between_existing_tumors = distance_between_existing_tumors
        self.distance_between_queen_tumors = distance_between_queen_tumors
        self.min_distance_between_existing_tumors = min_distance_between_existing_tumors
        self.should_tumors_block_expansions = should_tumors_block_expansions
        self.creep_targets = creep_targets
        self.spread_style = spread_style
        self.rally_point = rally_point
        self.target_perc_coverage = target_perc_coverage
        self.first_tumor_position = first_tumor_position
        self.prioritize_creep = prioritize_creep


class InjectQueen(Policy):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
