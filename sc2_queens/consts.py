from typing import Set
from enum import Enum, auto


class QueenRoles(Enum):
    Creep = auto()
    Defence = auto()
    Inject = auto()


class QueenPolicyKeys(Enum):
    CreepQueens = "creep_queens"
    DefenceQueens = "defence_queens"
    InjectQueens = "inject_queens"
    Active = "active"
    MaxQueens = "max"
    Priority = "priority"
    DefendAir = "defend_against_air"
    DefendGround = "defend_against_ground"
    ActiveUntil = "active_until"
    TumorsBlockExpos = "tumors_block_expansions"
    DistanceBetweenQueenTumors = "distance_between_queen_tumors"
    DistanceBetweenExistingTumors = "distance_between_existing_tumors"
    RallyPoint = "rally_point"
