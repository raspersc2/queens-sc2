from typing import Set
from enum import Enum, auto
from sc2.ids.unit_typeid import UnitTypeId as UnitID

CREEP_POLICY: str = "creep_policy"
CREEP_DROPPERLORD_POLICY: str = "creep_dropperlord_policy"
DEFENCE_POLICY: str = "defence_policy"
INJECT_POLICY: str = "inject_policy"
NYDUS_POLICY: str = "nydus_policy"
QUEEN_TURN_RATE: float = 999.8437


class QueenRoles(Enum):
    Creep = auto()
    Defence = auto()
    Inject = auto()


CHANGELING_TYPES: Set[UnitID] = {
    UnitID.CHANGELING,
    UnitID.CHANGELINGMARINE,
    UnitID.CHANGELINGMARINESHIELD,
    UnitID.CHANGELINGZEALOT,
    UnitID.CHANGELINGZERGLING,
    UnitID.CHANGELINGZERGLINGWINGS,
}

GROUND_TOWNHALL_TYPES: Set[UnitID] = {
    UnitID.HATCHERY,
    UnitID.HIVE,
    UnitID.LAIR,
    UnitID.NEXUS,
    UnitID.COMMANDCENTER,
    UnitID.ORBITALCOMMAND,
    UnitID.PLANETARYFORTRESS,
}


UNITS_TO_TRANSFUSE: Set[UnitID] = {
    UnitID.BROODLORD,
    UnitID.CORRUPTOR,
    UnitID.HYDRALISK,
    UnitID.LURKER,
    UnitID.MUTALISK,
    UnitID.QUEEN,
    UnitID.RAVAGER,
    UnitID.ROACH,
    UnitID.OVERSEER,
    UnitID.OVERLORD,
    UnitID.OVERLORDTRANSPORT,
    UnitID.SWARMHOSTMP,
    UnitID.ULTRALISK,
    UnitID.SPINECRAWLER,
    UnitID.SPORECRAWLER,
    UnitID.EVOLUTIONCHAMBER,
    UnitID.HATCHERY,
    UnitID.LAIR,
    UnitID.HIVE,
    UnitID.VIPER,
    UnitID.INFESTOR,
    UnitID.SPAWNINGPOOL,
    UnitID.NYDUSCANAL,
    UnitID.NYDUSNETWORK,
}


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
