from typing import Optional

from sc2 import BotAI
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units
import numpy as np

from queens_sc2.cache import property_cache_once_per_frame
from queens_sc2.queen_control.base_unit import BaseUnit
from queens_sc2.policy import Policy


class Nydus(BaseUnit):
    def __init__(self, bot: BotAI, nydus_policy: Policy, map_data: Optional["MapData"]):
        super().__init__(bot, map_data)
        self.policy = nydus_policy

    @property_cache_once_per_frame
    def enemy_flying_units_near_nydus_target(self) -> Units:
        return self.bot.enemy_units.filter(
            lambda u: u.distance_to(self.policy.nydus_target) < 40
        )

    @property_cache_once_per_frame
    def enemy_ground_units_near_nydus_target(self) -> Units:
        return self.bot.enemy_units.filter(
            lambda u: u.distance_to(self.policy.nydus_target) < 40
            and u.type_id not in {UnitID.EGG, UnitID.LARVA}
        )

    @property_cache_once_per_frame
    def enemy_structures_near_nydus_target(self) -> Units:
        return self.bot.enemy_structures.filter(
            lambda u: u.distance_to(self.policy.nydus_target) < 40
        )

    @property_cache_once_per_frame
    def nyduses_close_to_target(self) -> Units:
        return self.bot.structures.filter(
            lambda s: s.type_id in {UnitID.NYDUSCANAL, UnitID.NYDUSNETWORK}
            and s.distance_to(self.policy.nydus_target) < 40
        )

    @property_cache_once_per_frame
    def nyduses_far_from_target(self) -> Units:
        return self.bot.structures.filter(
            lambda s: s.type_id in {UnitID.NYDUSCANAL, UnitID.NYDUSNETWORK}
            and s.distance_to(self.policy.nydus_target) > 50
        )

    async def handle_unit(
        self,
        air_threats_near_bases: Units,
        ground_threats_near_bases: Units,
        priority_enemy_units: Units,
        unit: Unit,
        th_tag: int = 0,
        grid: Optional[np.ndarray] = None,
        nydus_networks: Optional[Units] = None,
        nydus_canals: Optional[Units] = None,
    ) -> None:
        canal: Optional[Unit] = None
        network: Optional[Unit] = None
        # canal is what we place else where on the map
        if nydus_canals:
            canal = nydus_canals.closest_to(self.policy.nydus_target)
        # network is what is morphed from a drone
        if nydus_networks:
            network = nydus_networks.closest_to(self.bot.start_location)

        unit_distance_to_target: float = unit.distance_to(self.policy.nydus_target)

        if canal and network:
            await self._manage_nydus_attack(
                canal, network, unit, unit_distance_to_target, grid
            )

    def set_attack_target(self, target: Point2) -> None:
        """
        Set an attack target so if nydus queen has no targets left, she can keep attacking
        """
        self.policy.attack_target = target

    def set_nydus_target(self, nydus_target: Point2) -> None:
        self.policy.nydus_target = nydus_target

    def update_policy(self, policy: Policy) -> None:
        self.policy = policy

    async def _manage_nydus_attack(
        self,
        canal: Unit,
        network: Unit,
        unit: Unit,
        unit_distance_to_target: float,
        grid: Optional[np.ndarray] = None,
    ) -> None:
        """
        Get a Queen through the nydus and out the other side!
        @param canal: The canal is the worm placed on the map
        @param network: This is built at home
        @param unit: In this case, the queen we want to move through
        @param unit_distance_to_target:
        @return:
        """
        # user does not have some predefined nydus logic, so we unload the proxy canal for them
        if len(canal.passengers_tags) > 0 and not self.policy.nydus_move_function:
            canal(AbilityId.UNLOADALL_NYDUSWORM)

        # worm has popped somewhere, but we are waiting for it to finish, move next to network ready to go
        # usually we want queens last in anyway, so this gives a chance for other units to enter the nydus
        if not canal.is_ready and unit.distance_to(canal) > 30:
            unit.move(network.position)
        # both canal and network must be ready
        else:
            # unit needs to go through the nydus
            if unit_distance_to_target > 45 and unit.distance_to(network) < 70:
                # user has some custom code for moving units through nydus
                if self.policy.nydus_move_function:
                    self.policy.nydus_move_function(unit, self.policy.nydus_target)
                # manage this ourselves
                else:
                    unit.smart(network)
            # else queen should micro on the other side
            # remember that all queens already have transfuse code baked in
            else:
                # queen has enough energy for a transfuse and a tumor, so put a tumor down where she currently is
                if unit.energy >= 75 and self.bot.has_creep(unit.position):
                    # check if there are too many tumors already
                    tumors: Units = self.bot.structures.filter(
                        lambda s: s.type_id
                        in {UnitID.CREEPTUMORBURROWED, UnitID.CREEPTUMORQUEEN}
                        and s.distance_to(unit) < 15
                    )
                    if tumors.amount < 7:
                        unit(AbilityId.BUILD_CREEPTUMOR_QUEEN, unit.position)
                if unit.is_using_ability(AbilityId.BUILD_CREEPTUMOR_QUEEN):
                    return
                # get priority target, ie: target the flying enemies first
                target: Optional[Unit] = self._get_target_from_close_enemies(unit)
                if target:
                    if self.attack_ready(unit, target):
                        unit.attack(target)
                    elif self.map_data and grid is not None:
                        await self.move_towards_safe_spot(unit, grid)
                    else:
                        distance: float = (
                            unit.ground_range + unit.radius + target.radius
                        )
                        move_to: Point2 = target.position.towards(unit, distance)
                        if self.bot.in_pathing_grid(move_to):
                            unit.move(move_to)

                # there are targets, but nothing in range so move towards the nydus target
                else:
                    if not self.bot.is_visible(self.policy.nydus_target):
                        unit.move(self.policy.nydus_target)
                    # TODO: In the future, this is where we would want the queens to come home
                    #   At the moment a nydus queen is on a one way trip
                    else:
                        await self.do_queen_offensive_micro(
                            unit, self.policy.attack_target
                        )

    def _get_target_from_close_enemies(self, unit: Unit) -> Unit:
        """Try to find something in range of the queen"""
        if (
            self.enemy_flying_units_near_nydus_target
            and self.enemy_flying_units_near_nydus_target.in_attack_range_of(unit)
        ):
            return self.enemy_flying_units_near_nydus_target.closest_to(unit)
        if (
            self.enemy_ground_units_near_nydus_target
            and self.enemy_ground_units_near_nydus_target.in_attack_range_of(unit)
        ):
            return self.enemy_ground_units_near_nydus_target.closest_to(unit)
        if (
            self.enemy_structures_near_nydus_target
            and self.enemy_structures_near_nydus_target.in_attack_range_of(unit)
        ):
            return self.enemy_structures_near_nydus_target.closest_to(unit)
