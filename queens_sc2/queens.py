from typing import DefaultDict, Dict, List, Optional, Set, Tuple, Union
from collections import defaultdict
import numpy as np
from sc2 import BotAI
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.position import Point2, Point3
from sc2.unit import Unit
from sc2.units import Units
from queens_sc2.cache import property_cache_once_per_frame
from queens_sc2.consts import (
    CREEP_POLICY,
    CREEP_DROPPERLORD_POLICY,
    DEFENCE_POLICY,
    INJECT_POLICY,
    NYDUS_POLICY,
    QueenRoles,
)
from queens_sc2.kd_trees import KDTrees
from queens_sc2.queen_control.base_unit import BaseUnit
from queens_sc2.queen_control.creep import Creep
from queens_sc2.queen_control.creep_dropperlord import CreepDropperlord
from queens_sc2.queen_control.defence import Defence
from queens_sc2.queen_control.inject import Inject
from queens_sc2.queen_control.nydus import Nydus
from queens_sc2.policy import (
    DefenceQueen,
    CreepQueen,
    CreepDropperlordQueen,
    InjectQueen,
    NydusQueen,
    Policy,
)


class Queens:
    # optional sc2 map analysis plug in https://github.com/eladyaniv01/SC2MapAnalysis
    map_data: "MapData"
    """
    Main entry point for queen_control-sc2, with optional support for SC2 Map Analyzer
    Example setup with map_analyzer:
    (follow setup instructions at https://github.com/eladyaniv01/SC2MapAnalysis)
    ```
    from sc2 import BotAI
    from MapAnalyzer import MapData
    from queens_sc2.queen_control import Queens
    
    class ZergBot(BotAI):
        async def on_start(self) -> None:
            self.map_data = MapData(self)  # where self is your BotAI object from python-sc2
            self.queen_control = Queens(
                self, queen_policy=self.my_policy, map_data=self.map_data
            )
            
        async def on_step(self, iteration: int) -> None:
            ground_grid: np.ndarray = self.map_data.get_pyastar_grid()
            # you may want to add cost etc depending on your bot, 
            # depending on usecase it may not need a fresh grid every step
            await self.queen_control.manage_queens(iteration, grid=ground_grid)
    
    ```
    
    Though all features of queen_control-sc2 will work without SC2 Map Analyzer, for example:
    ```
    from sc2 import BotAI
    from queens_sc2.queen_control import Queens
    
    class ZergBot(BotAI):
        async def on_start(self) -> None:
            self.queen_control = Queens(self, queen_policy=self.my_policy)
            
        async def on_step(self, iteration: int) -> None:
            await self.queen_control.manage_queens(iteration)
    
    ```
    """

    TRANSFUSE_ENERGY_COST: int = 50

    def __init__(
        self,
        bot: BotAI,
        debug: bool = False,
        queen_policy: Dict = None,
        map_data: Optional["MapData"] = None,
        control_canal: bool = True,
    ):
        self.kd_trees: KDTrees = KDTrees(bot)
        self.bot: BotAI = bot
        self.debug: bool = debug
        self.assigned_queen_tags: Set[int] = set()
        self.creep_queen_tags: List[int] = []
        self.creep_dropperlod_tags: List[int] = []
        self.defence_queen_tags: List[int] = []
        self.inject_targets: Dict[int, int] = {}
        self.nydus_queen_tags: List[int] = []
        self.control_canal: bool = control_canal

        self.policies: Dict[str, Policy] = self._read_queen_policy(queen_policy)
        self.creep: Creep = Creep(
            bot, self.kd_trees, self.policies[CREEP_POLICY], map_data
        )
        self.creep_dropperlord: CreepDropperlord = CreepDropperlord(
            bot, self.kd_trees, self.policies[CREEP_DROPPERLORD_POLICY], map_data
        )
        self.defence: Defence = Defence(
            bot, self.kd_trees, self.policies[DEFENCE_POLICY], map_data
        )
        self.inject: Inject = Inject(
            bot, self.kd_trees, self.policies[INJECT_POLICY], map_data
        )
        self.nydus: Nydus = Nydus(
            bot, self.kd_trees, self.policies[NYDUS_POLICY], map_data
        )
        self.transfuse_dict: Dict[int] = {}
        # key: unit tag, value: when to expire so unit can be transfused again
        self.targets_being_transfused: Dict[int, float] = {}
        self.creep.update_creep_map()
        self.unit_controllers: DefaultDict[int, BaseUnit] = defaultdict(BaseUnit)
        self.map_data = map_data

    @property_cache_once_per_frame
    def nydus_canals(self) -> Units:
        return self.bot.structures(UnitID.NYDUSCANAL)

    @property_cache_once_per_frame
    def nydus_networks(self) -> Units:
        return self.bot.structures(UnitID.NYDUSNETWORK)

    async def manage_queens(
        self,
        iteration: int,
        air_threats_near_bases: Optional[Units] = None,
        ground_threats_near_bases: Optional[Units] = None,
        queens: Optional[Units] = None,
        air_grid: Optional[np.ndarray] = None,
        avoidance_grid: Optional[np.ndarray] = None,
        grid: Optional[np.ndarray] = None,
        natural_position: Optional[Point2] = None,
        unselectable_dropperlords: Optional[Union[Dict, Set]] = None,
    ) -> None:
        """
        This is the main method your bot will call
        Args:
            @param iteration: Current step / frame number
            @param air_threats_near_bases: Air threats, queens-sc2 will calculate this if `None`
            @param ground_threats_near_bases: Ground threats, queens-sc2 will calculate this if `None`
            @param queens: Collection of queens `queens-sc2` should manage, will take all queens otherwise
            @param air_grid: Air grid from SC2MapAnalyzer, used for queen droppperlord pathfinding
                                (map_data should be plugged in via the constructor)
            @param avoidance_grid: Ground avoidance grid from SC2MapAnalyzer, used to keep queens safe
                                (map_data should be plugged in via the constructor)
            @param grid: Ground grid from SC2MapAnalyzer, used for Queen micro and creep spread
                                (map_data should be plugged in via the constructor)
            @param natural_position: Own natural, not currently used
            @param unselectable_dropperlords: Tags of dropperlords queens-sc2 shouldn't steal
                                            If passing a dict, the keys should be the dropperlord tags
        """
        self.kd_trees.update()
        if self.defence.policy.pass_own_threats:
            air_threats: Units = air_threats_near_bases
            ground_threats: Units = ground_threats_near_bases
        else:
            air_threats: Units = self.defence.enemy_air_threats
            ground_threats: Units = self.defence.enemy_ground_threats

        if self.map_data:
            if air_grid is None:
                air_grid = self.map_data.get_clean_air_grid()
            if grid is None:
                grid = self.map_data.get_pyastar_grid()
            if avoidance_grid is None:
                avoidance_grid = self.map_data.get_pyastar_grid()

        if queens is None:
            queens: Units = self.bot.units(UnitID.QUEEN)

        if iteration % 8 == 0:
            self.creep.update_creep_map()

        if iteration % 128 == 0:
            Creep.creep_coverage.fget.cache_clear()

        if (
            self.creep.creep_coverage < 50
            or iteration % int(self.creep.creep_coverage / 8) == 0
        ):
            await self.creep.spread_existing_tumors()

        await self._handle_queens(
            air_threats,
            ground_threats,
            queens,
            air_grid,
            avoidance_grid,
            grid,
            natural_position,
            unselectable_dropperlords,
        )

        if self.control_canal and self.nydus_canals.ready:
            for nydus in self.nydus_canals.ready:
                nydus(AbilityId.UNLOADALL_NYDUSWORM)

        if self.debug:
            await self._draw_debug_info()

    def remove_unit(self, unit_tag) -> None:
        self.creep_queen_tags = [
            tag for tag in self.creep_queen_tags if tag != unit_tag
        ]
        self.defence_queen_tags = [
            tag for tag in self.defence_queen_tags if tag != unit_tag
        ]
        self.nydus_queen_tags = [
            tag for tag in self.nydus_queen_tags if tag != unit_tag
        ]
        try:
            del self.inject_targets[unit_tag]
        except KeyError:
            pass
        # here we check if townhall was destroyed
        for k in self.inject_targets.copy():
            if self.inject_targets[k] == unit_tag:
                del self.inject_targets[k]
                # also assign the dead townhall's queen a new role if she is alive
                queens: Units = self.bot.units(UnitID.QUEEN).tags_in([k])
                if queens:
                    self.assigned_queen_tags.remove(queens.first.tag)
                    self._assign_queen_role(queens.first)
        if unit_tag in self.assigned_queen_tags:
            self.assigned_queen_tags.remove(unit_tag)

        # dropperlord tags
        if unit_tag in self.creep_dropperlod_tags:
            self.creep_dropperlod_tags.remove(unit_tag)

        if unit_tag == self.creep_dropperlord.dropperlord_tag:
            self.creep_dropperlord.dropperlord_tag = 0
            self.creep_dropperlod_tags = []

    def set_new_policy(self, queen_policy, reset_roles: bool = True) -> None:
        self.policies = self._read_queen_policy(queen_policy)
        if reset_roles:
            self.reset_roles()

        self.creep.update_policy(self.policies[CREEP_POLICY])
        self.creep_dropperlord.update_policy(self.policies[CREEP_DROPPERLORD_POLICY])
        self.defence.update_policy(self.policies[DEFENCE_POLICY])
        self.inject.update_policy(self.policies[INJECT_POLICY])
        self.nydus.update_policy(self.policies[NYDUS_POLICY])

    def reset_roles(self) -> None:
        self.assigned_queen_tags = set()
        self.creep_queen_tags = []
        self.defence_queen_tags = []
        self.inject_targets.clear()

    def update_attack_target(self, attack_target: Point2) -> None:
        self.defence.set_attack_target(attack_target)
        self.nydus.set_attack_target(attack_target)

    def update_creep_targets(
        self, creep_targets: Union[List[Point2], List[Tuple[Point2, Point2]]]
    ) -> None:
        self.creep.set_creep_targets(creep_targets)

    def update_nydus_target(self, nydus_target: Point2) -> None:
        self.nydus.set_nydus_target(nydus_target)

    async def _handle_queens(
        self,
        air_threats: Units,
        ground_threats: Units,
        queens: Units,
        air_grid: Optional[np.ndarray],
        avoidance_grid: Optional[np.ndarray],
        grid: Optional[np.ndarray],
        natural_position: Optional[Point2],
        unselectable_dropperlords: Optional[Union[Dict, Set]] = None,
    ):
        all_close_threats: Units = air_threats + ground_threats
        creep_priority_enemy_units: Units = self._get_priority_enemy_units(
            all_close_threats, self.creep.policy
        )
        defence_priority_enemy_units: Units = self._get_priority_enemy_units(
            all_close_threats, self.defence.policy
        )
        inject_priority_enemy_units: Units = self._get_priority_enemy_units(
            all_close_threats, self.inject.policy
        )

        """ Main Queen loop """
        for queen in queens:
            if queen.tag in self.creep_dropperlod_tags:
                continue
            self._assign_queen_role(queen)
            # if any queen has more than 50 energy, she may transfuse at any time it's required
            if queen.energy >= self.TRANSFUSE_ENERGY_COST:
                # _handle_transfuse method will return True if queen will transfuse
                if await self._handle_transfuse(queen):
                    continue
            th_tag: int = (
                self.inject_targets[queen.tag]
                if queen.tag in self.inject_targets
                else 0
            )
            priority_threats: Units = (
                inject_priority_enemy_units
                if queen.tag in self.inject_targets
                else (
                    defence_priority_enemy_units
                    if queen.tag in self.defence_queen_tags
                    else creep_priority_enemy_units
                )
            )
            if queen.tag in self.unit_controllers:
                await self.unit_controllers[queen.tag].handle_unit(
                    air_threats_near_bases=air_threats,
                    ground_threats_near_bases=ground_threats,
                    priority_enemy_units=priority_threats,
                    unit=queen,
                    th_tag=th_tag,
                    avoidance_grid=avoidance_grid,
                    grid=grid,
                    nydus_networks=self.nydus_networks,
                    nydus_canals=self.nydus_canals,
                    natural_position=natural_position,
                )

        if len(self.creep_dropperlod_tags) > 0:
            await self.creep_dropperlord.handle_queen_dropperlord(
                creep_map=self.creep.creep_map,
                unit_tag=self.creep_dropperlod_tags[0],
                queens=queens,
                air_grid=air_grid,
                avoidance_grid=avoidance_grid,
                grid=grid,
                unselectable_dropperlords=unselectable_dropperlords,
            )

    async def _handle_transfuse(self, queen: Unit) -> bool:
        """Deal with a queen transfusing"""
        if queen.is_using_ability(AbilityId.TRANSFUSION_TRANSFUSION):
            return True
        # clear out targets from the dict after a short interval so they may be transfused again
        transfuse_tags = list(self.targets_being_transfused.keys())
        for tag in transfuse_tags:
            if self.targets_being_transfused[tag] < self.bot.time:
                self.targets_being_transfused.pop(tag)

        transfuse_target: Unit = self.defence.get_transfuse_target(
            queen.position, self.targets_being_transfused
        )
        if transfuse_target and transfuse_target is not queen:
            queen(AbilityId.TRANSFUSION_TRANSFUSION, transfuse_target)
            self.targets_being_transfused[transfuse_target.tag] = self.bot.time + 0.3
            return True
        return False

    def _assign_queen_role(self, queen: Unit) -> None:
        """
        If queen does not have role, work out from the policy what role it should have
        If 2 nydus worms are present, steal queen_control from the relevant role set in policy
        :param queen:
        :type queen:
        :return:
        :rtype:
        """
        # If this queen has a role, we might want to steal it for the nydus, or for a creep dropperlord
        self._check_nydus_role(queen)
        self._check_creep_dropperlord_role(queen)

        if self._queen_has_role(queen):
            return
        # if there are priority clashes, revert to:
        # inject, creep, defence
        # if there is a priority, assign it to the relevant group
        priorities: List[QueenRoles] = []
        ready_townhalls: Units = self.bot.townhalls.ready
        ths_without_queen: Units = ready_townhalls.filter(
            lambda townhall: townhall.tag not in self.inject_targets.values()
        )
        # work out which roles are of priority
        for key, value in self.policies.items():
            if value.active and value.priority:
                max_queens: int = (
                    value.priority if type(value.priority) == int else value.max_queens
                )
                if key == CREEP_POLICY and len(self.creep_queen_tags) < max_queens:
                    priorities.append(QueenRoles.Creep)
                elif (
                    key == DEFENCE_POLICY and len(self.defence_queen_tags) < max_queens
                ):
                    priorities.append(QueenRoles.Defence)
                elif key == INJECT_POLICY and len(self.inject_targets) < min(
                    max_queens, ready_townhalls.amount
                ):
                    priorities.append(QueenRoles.Inject)
        if QueenRoles.Inject in priorities and ths_without_queen:
            # pick th closest to queen, so she doesn't have to walk too far
            th: Unit = ths_without_queen.closest_to(queen)
            if th.tag not in self.inject_targets.values():
                self.unit_controllers[queen.tag] = self.inject
                self.inject_targets[queen.tag] = th.tag
                self.assigned_queen_tags.add(queen.tag)
        elif QueenRoles.Creep in priorities:
            self.unit_controllers[queen.tag] = self.creep
            self.creep_queen_tags.append(queen.tag)
            self.assigned_queen_tags.add(queen.tag)
        elif QueenRoles.Defence in priorities:
            self.unit_controllers[queen.tag] = self.defence
            self.defence_queen_tags.append(queen.tag)
            self.assigned_queen_tags.add(queen.tag)
        # if we get to here, then assign to inject, then creep then defence
        else:
            if (
                len(self.inject_targets)
                < min(self.policies[INJECT_POLICY].max_queens, ready_townhalls.amount)
                and self.policies[INJECT_POLICY].active
            ):
                if ths_without_queen:
                    # pick th closest to queen
                    th: Unit = ths_without_queen.closest_to(queen)
                    self.unit_controllers[queen.tag] = self.inject
                    self.inject_targets[queen.tag] = th.tag
                    self.assigned_queen_tags.add(queen.tag)
            elif (
                len(self.creep_queen_tags) < self.policies[CREEP_POLICY].max_queens
                and self.policies[CREEP_POLICY].active
            ):
                self.unit_controllers[queen.tag] = self.creep
                self.creep_queen_tags.append(queen.tag)
                self.assigned_queen_tags.add(queen.tag)
            # leftover queen_control get assigned to defence regardless, otherwise queen would do nothing
            else:
                self.unit_controllers[queen.tag] = self.defence
                self.defence_queen_tags.append(queen.tag)
                self.assigned_queen_tags.add(queen.tag)

    def _check_creep_dropperlord_role(self, queen: Unit) -> None:
        """Steal a queen from the creep queens"""
        if (
            queen.tag not in self.creep_queen_tags
            or len(self.creep_dropperlod_tags)
            >= self.creep_dropperlord.policy.max_queens
        ):
            return

        lair_tech_ready: bool = False
        for th in self.bot.townhalls:
            if (th.type_id == UnitID.LAIR and th.is_ready) or th.type_id == UnitID.HIVE:
                lair_tech_ready = True
                break

        if lair_tech_ready:
            self.remove_unit(queen.tag)
            self.assigned_queen_tags.add(queen.tag)
            self.creep_dropperlod_tags.append(queen.tag)
            if queen.tag in self.unit_controllers:
                del self.unit_controllers[queen.tag]

    def _check_nydus_role(self, queen: Unit) -> None:
        """
        If there are nydus's we may want to steal this queen for the nydus
        Or if this queen already has a nydus role, we should remove the nydus role if required
        """
        steal_from: Set[UnitID] = self.nydus.policy.steal_from
        # check if queens should be assigned to nydus role, is there a network and a canal?
        if (
            self.nydus_networks
            and self.nydus_canals
            and self.nydus.policy.active
            and len(self.nydus_queen_tags) < self.nydus.policy.max_queens
            and queen.tag not in self.nydus_queen_tags
            and queen.tag in self.assigned_queen_tags
        ):
            # queen can only be in one role
            role_to_check: QueenRoles = (
                QueenRoles.Defence
                if queen.tag in self.defence_queen_tags
                else (
                    QueenRoles.Creep
                    if queen.tag in self.creep_queen_tags
                    else QueenRoles.Defence
                )
            )
            # queen role is in one of the allowed roles to steal from
            if role_to_check in steal_from:
                self.remove_unit(queen.tag)
                self.assigned_queen_tags.add(queen.tag)
                self.nydus_queen_tags.append(queen.tag)
                self.unit_controllers[queen.tag] = self.nydus

        # TODO: Work out how to handle aborting a Nydus:
        #   - Policy option for when Queen goes back into canal if too much danger?
        #   - What if the canal dies and the queen has an escape path?
        # At the moment assigning a Queen to Nydus is a one way trip
        # Here we only handle, Queens being assigned to Nydus and then the canal getting destroyed in the meantime
        if (
            queen.tag in self.nydus_queen_tags
            and queen.distance_to(self.nydus.policy.nydus_target) > 50
            and not self.nydus_canals
        ):
            # removing should be enough, queen then should be given a new role automatically
            self.remove_unit(queen.tag)

    def _queen_has_role(self, queen: Unit) -> bool:
        """
        Checks if we know about queen
        """
        return queen.tag in self.assigned_queen_tags

    def _read_queen_policy(self, queen_policy: Dict) -> Dict[str, Policy]:
        """
        Read the queen policy the user passed in, add default
        params for missing values

        :param queen_policy:
        :type queen_policy: Dict
        :return: new policy with default params for missing values
        :rtype: Dict
        """
        # handle user not passing in a policy
        _queen_policy: Dict = queen_policy if queen_policy else {}
        cq_policy = _queen_policy.get("creep_queens", {})
        cdq_policy = _queen_policy.get("creep_dropperlord_queens", {})
        dq_policy = _queen_policy.get("defence_queens", {})
        iq_policy = _queen_policy.get("inject_queens", {})
        nq_policy = _queen_policy.get("nydus_queens", {})

        creep_queen_policy = CreepQueen(
            active=cq_policy.get("active", True),
            max_queens=cq_policy.get("max", 2),
            priority=cq_policy.get("priority", 1),
            defend_against_air=cq_policy.get("defend_against_air", True),
            defend_against_ground=cq_policy.get("defend_against_ground", False),
            distance_between_existing_tumors=cq_policy.get(
                "distance_between_existing_tumors", 10
            ),
            distance_between_queen_tumors=cq_policy.get(
                "distance_between_queen_tumors", 7
            ),
            min_distance_between_existing_tumors=cq_policy.get(
                "min_distance_between_existing_tumors", 3
            ),
            should_tumors_block_expansions=cq_policy.get(
                "should_tumors_block_expansions", False
            ),
            creep_targets=cq_policy.get(
                "creep_targets",
                self._path_expansion_distances(),
            ),
            spread_style=cq_policy.get("spread_style", "targeted"),
            rally_point=cq_policy.get(
                "rally_point",
                self.bot.start_location,
            ),
            target_perc_coverage=cq_policy.get(
                "target_perc_coverage",
                75.0,
            ),
            first_tumor_position=cq_policy.get(
                "first_tumor_position",
                None,
            ),
            pass_own_threats=cq_policy.get(
                "pass_own_threats",
                False,
            ),
            prioritize_creep=cq_policy.get("prioritize_creep", lambda: False),
            priority_defence_list=cq_policy.get("priority_defence_list", set()),
        )

        creep_dropperlord_queen_policy = CreepDropperlordQueen(
            active=cdq_policy.get("active", True),
            max_queens=cdq_policy.get("max", 1),
            priority=cdq_policy.get("priority", False),
            defend_against_air=cdq_policy.get("defend_against_air", False),
            defend_against_ground=cdq_policy.get("defend_against_ground", False),
            pass_own_threats=cdq_policy.get(
                "pass_own_threats",
                False,
            ),
            priority_defence_list=cdq_policy.get("priority_defence_list", set()),
            target_expansions=cdq_policy.get("target_expansions", []),
        )

        defence_queen_policy = DefenceQueen(
            active=dq_policy.get("active", True),
            max_queens=dq_policy.get("max", 6),
            priority=dq_policy.get("priority", False),
            defend_against_air=dq_policy.get("defend_against_air", True),
            defend_against_ground=dq_policy.get("defend_against_ground", True),
            attack_condition=dq_policy.get("attack_condition", lambda: False),
            attack_target=dq_policy.get(
                "attack_target", self.bot.enemy_start_locations[0]
            ),
            rally_point=dq_policy.get(
                "rally_point",
                self.bot.start_location,
            ),
            pass_own_threats=dq_policy.get(
                "pass_own_threats",
                False,
            ),
            priority_defence_list=dq_policy.get("priority_defence_list", set()),
        )

        inject_queen_policy = InjectQueen(
            active=iq_policy.get("active", True),
            max_queens=iq_policy.get("max", 6),
            priority=iq_policy.get("priority", False),
            defend_against_air=iq_policy.get("defend_against_air", False),
            defend_against_ground=iq_policy.get("defend_against_ground", False),
            pass_own_threats=iq_policy.get(
                "pass_own_threats",
                False,
            ),
            priority_defence_list=iq_policy.get("priority_defence_list", set()),
        )

        nydus_queen_policy = NydusQueen(
            active=nq_policy.get("active", True),
            max_queens=nq_policy.get("max", 2),
            priority=nq_policy.get("priority", False),
            # TODO: user might want the queen to come home to defend, atm this does nothing
            defend_against_air=nq_policy.get("defend_against_air", False),
            defend_against_ground=nq_policy.get("defend_against_ground", False),
            pass_own_threats=nq_policy.get(
                "pass_own_threats",
                False,
            ),
            priority_defence_list=nq_policy.get("priority_defence_list", set()),
            attack_target=nq_policy.get(
                "attack_target", self.bot.enemy_start_locations[0]
            ),
            nydus_move_function=nq_policy.get("nydus_move_function", None),
            nydus_target=nq_policy.get(
                "nydus_target", self.bot.enemy_start_locations[0]
            ),
            steal_from=nq_policy.get("steal_from", {QueenRoles.Defence}),
        )

        policies = {
            CREEP_POLICY: creep_queen_policy,
            CREEP_DROPPERLORD_POLICY: creep_dropperlord_queen_policy,
            DEFENCE_POLICY: defence_queen_policy,
            INJECT_POLICY: inject_queen_policy,
            NYDUS_POLICY: nydus_queen_policy,
        }

        return policies

    @staticmethod
    def _get_priority_enemy_units(
        enemy_threats: Units, policy: Policy
    ) -> Optional[Units]:
        if enemy_threats and len(policy.priority_defence_list) != 0:
            priority_threats: Units = enemy_threats(policy.priority_defence_list)
            return priority_threats

    def _path_expansion_distances(self) -> List[Point2]:
        """
        If user passes no creep targets in policy, we use expansion locations
        """
        expansion_distances = []
        spawn_loc = self.bot.start_location
        for el in self.bot.expansion_locations_list:
            if (
                Point2(spawn_loc).position.distance_to(el)
                < self.bot.EXPANSION_GAP_THRESHOLD
            ):
                continue

            expansion_distances.append(el)
        return expansion_distances

    async def _draw_debug_info(self) -> None:
        self.bot.client.debug_text_screen(
            f"Creep Queens Amount: {str(len(self.creep_queen_tags))}, "
            f"Policy Amount: {str(self.policies[CREEP_POLICY].max_queens)}",
            pos=(0.2, 0.6),
            size=13,
            color=(0, 255, 255),
        )
        self.bot.client.debug_text_screen(
            f"Defence Queens Amount: {str(len(self.defence_queen_tags))}, "
            f"Policy Amount (this can go over): {str(self.policies[DEFENCE_POLICY].max_queens)}",
            pos=(0.2, 0.62),
            size=13,
            color=(0, 255, 255),
        )
        self.bot.client.debug_text_screen(
            f"Inject Queens Amount: {str(len(self.inject_targets.keys()))}, "
            f"Policy Amount: {str(self.policies[INJECT_POLICY].max_queens)}",
            pos=(0.2, 0.64),
            size=13,
            color=(0, 255, 255),
        )
        self.bot.client.debug_text_screen(
            f"Nydus Queens Amount: {str(len(self.nydus_queen_tags))}, "
            f"Policy Amount: {str(self.policies[NYDUS_POLICY].max_queens)}",
            pos=(0.2, 0.66),
            size=13,
            color=(0, 255, 255),
        )

        self.bot.client.debug_text_screen(
            f"Creep Coverage: {str(self.creep.creep_coverage)}%",
            pos=(0.2, 0.68),
            size=13,
            color=(0, 255, 255),
        )

        self.bot.client.debug_text_screen(
            f"Priority defend against: {str(self.defence.policy.priority_defence_list)}",
            pos=(0.2, 0.70),
            size=13,
            color=(0, 255, 255),
        )

        queens: Units = self.bot.units(UnitID.QUEEN)
        if queens:
            for queen in queens:
                # don't use elif, to check for bugs (queen more than one role)
                if queen.tag in self.creep_queen_tags:
                    self._draw_on_world(queen.position, f"CREEP {queen.tag}")
                if queen.tag in self.defence_queen_tags:
                    self._draw_on_world(queen.position, f"DEFENCE {queen.tag}")
                if queen.tag in self.inject_targets:
                    self._draw_on_world(queen.position, f"INJECT {queen.tag}")
                if queen.tag in self.nydus_queen_tags:
                    self._draw_on_world(queen.position, f"NYDUS {queen.tag}")

        tumors: Units = self.bot.structures.filter(
            lambda s: s.type_id == UnitID.CREEPTUMORBURROWED
            and s.tag not in self.creep.used_tumors
        )
        if tumors:
            for tumor in tumors:
                self._draw_on_world(tumor.position, f"TUMOR")

        self._draw_on_world(
            self.creep_dropperlord.current_creep_target, "DROPPERLORD CREEP TARGET"
        )
        for potential_target in self.creep_dropperlord.creep_targets:
            self._draw_on_world(
                potential_target,
                f"{potential_target} POTENTIAL DROPPERLORD CREEP TARGET",
            )

    def _draw_on_world(self, pos: Point2, text: str) -> None:
        z_height: float = self.bot.get_terrain_z_height(pos)
        self.bot.client.debug_text_world(
            text,
            Point3((pos.x, pos.y, z_height)),
            color=(0, 255, 255),
            size=12,
        )
