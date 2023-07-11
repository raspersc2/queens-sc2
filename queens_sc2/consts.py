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


ALL_STRUCTURES: Set[UnitID] = {
    UnitID.ARMORY,
    UnitID.ASSIMILATOR,
    UnitID.ASSIMILATORRICH,
    UnitID.AUTOTURRET,
    UnitID.BANELINGNEST,
    UnitID.BARRACKS,
    UnitID.BARRACKSFLYING,
    UnitID.BARRACKSREACTOR,
    UnitID.BARRACKSTECHLAB,
    UnitID.BUNKER,
    UnitID.BYPASSARMORDRONE,
    UnitID.COMMANDCENTER,
    UnitID.COMMANDCENTERFLYING,
    UnitID.CREEPTUMOR,
    UnitID.CREEPTUMORBURROWED,
    UnitID.CREEPTUMORQUEEN,
    UnitID.CYBERNETICSCORE,
    UnitID.DARKSHRINE,
    UnitID.ELSECARO_COLONIST_HUT,
    UnitID.ENGINEERINGBAY,
    UnitID.EVOLUTIONCHAMBER,
    UnitID.EXTRACTOR,
    UnitID.EXTRACTORRICH,
    UnitID.FACTORY,
    UnitID.FACTORYFLYING,
    UnitID.FACTORYREACTOR,
    UnitID.FACTORYTECHLAB,
    UnitID.FLEETBEACON,
    UnitID.FORGE,
    UnitID.FUSIONCORE,
    UnitID.GATEWAY,
    UnitID.GHOSTACADEMY,
    UnitID.GREATERSPIRE,
    UnitID.HATCHERY,
    UnitID.HIVE,
    UnitID.HYDRALISKDEN,
    UnitID.INFESTATIONPIT,
    UnitID.LAIR,
    UnitID.LURKERDENMP,
    UnitID.MISSILETURRET,
    UnitID.NEXUS,
    UnitID.NYDUSCANAL,
    UnitID.NYDUSCANALATTACKER,
    UnitID.NYDUSCANALCREEPER,
    UnitID.NYDUSNETWORK,
    UnitID.ORACLESTASISTRAP,
    UnitID.ORBITALCOMMAND,
    UnitID.ORBITALCOMMANDFLYING,
    UnitID.PHOTONCANNON,
    UnitID.PLANETARYFORTRESS,
    UnitID.POINTDEFENSEDRONE,
    UnitID.PYLON,
    UnitID.PYLONOVERCHARGED,
    UnitID.RAVENREPAIRDRONE,
    UnitID.REACTOR,
    UnitID.REFINERY,
    UnitID.REFINERYRICH,
    UnitID.RESOURCEBLOCKER,
    UnitID.ROACHWARREN,
    UnitID.ROBOTICSBAY,
    UnitID.ROBOTICSFACILITY,
    UnitID.SENSORTOWER,
    UnitID.SHIELDBATTERY,
    UnitID.SPAWNINGPOOL,
    UnitID.SPINECRAWLER,
    UnitID.SPINECRAWLERUPROOTED,
    UnitID.SPIRE,
    UnitID.SPORECRAWLER,
    UnitID.SPORECRAWLERUPROOTED,
    UnitID.STARGATE,
    UnitID.STARPORT,
    UnitID.STARPORTFLYING,
    UnitID.STARPORTREACTOR,
    UnitID.STARPORTTECHLAB,
    UnitID.SUPPLYDEPOT,
    UnitID.SUPPLYDEPOTLOWERED,
    UnitID.TECHLAB,
    UnitID.TEMPLARARCHIVE,
    UnitID.TWILIGHTCOUNCIL,
    UnitID.ULTRALISKCAVERN,
    UnitID.WARPGATE,
}

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
