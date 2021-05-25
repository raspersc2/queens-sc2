# queens-sc2
queens-sc2 is a small customizable library to aid development of sc2 zerg bots developed with [python-sc2](https://github.com/BurnySc2/python-sc2). A challenge when developing zerg bots is effective queen management since queens have various roles including injecting, creep, defence and nydusing. 
queens-sc2 was created to allow zerg authors to rapidly develop a bot without being encumbered by queen management.
Using policies that can be updated at any time `queens-sc2` provides a lot of flexibility, whether that would be aggressive nydus play, defensive queens or a mass creep style

## Prerequisites 
It is expected the user has already installed [python-sc2](https://github.com/BurnySc2/python-sc2), `queens-sc2` also relies on numpy and scipy.

## Getting started
Clone or download this repository and put the `queens_sc2` directory in your bot folder like so:
```
MyBot
└───queens_sc2
│   └───queens_sc2 library files
└───your bot files and directories
```

Alternatively feel free to download [QueenBot](https://aiarena.net/bots/201/) from the AI Arena ladder and use that as a starting point for your own bot.

## Example bot file
Out of the box, the library will run without a policy but remember you have to build the queens yourself:
```python
from sc2 import BotAI
from queens_sc2.queens import Queens

class ZergBot(BotAI):
    queens: Queens
    
    async def on_start(self) -> None:
        self.queens = Queens(self)
        
    async def on_unit_destroyed(self, unit_tag: int):
        # checks if unit is a queen or th, library then handles appropriately
        self.queens.remove_unit(unit_tag)
        
    async def on_step(self, iteration: int) -> None:
        # call the queen library to handle our queen_control
        await self.queens.manage_queens(iteration)
        
        # can optionally pass in a custom selection of queen_control, ie:
        # queen_control: Units = self.units.tags_in(self.sc2_queen_tags)
        # await self.queen_control.manage_queens(iteration, queen_control)
        # if not the library will manage all queen_control automatically
        
        
        # the rest of my awesome bot ...
```

## Queen policy
To get the most out of this library, a custom queen policy can be passed to the library with the following options:
```python
queen_policy: Dict = {
  "creep_queens": {
      "active": bool,
      "max": int,
      "priority": Union[bool, int],
      "defend_against_air": bool,
      "defend_against_ground": bool,
      "distance_between_existing_tumors": int, # how far an existing tumor can spread to
      "distance_between_queen_tumors": int, # when deciding to lay a tumor, queen should leave this much distance between existing tumors
      "min_distance_between_existing_tumors": int, # min distance a tumor is allowed to spread to
      "should_tumors_block_expansions": bool,
      # If using Map Analyzer, a list of start and end goals can be passed in for creep targets, creep will then follow these paths
      "creep_targets": Union[List[Point2], List[Tuple[Point2, Point2]]], # library will cycle through these locations
      "spread_style": str, # "targeted" is default, or "random".
      "rally_point": Point2,
      "first_tumor_position": Optional[Point2],
      "prioritize_creep": Callable, # prioritize over defending bases if energy is available?
      "pass_own_threats": bool, # if set to True, library wont calculate enemy near bases, you should pass air and ground threats to manage_queens() method
      "priority_defence_list": Set[UnitID] # queen_control will prioritise defending these unit types over all other jobs
  },
  "defence_queens": {
      "active": bool,
      "max": int,
      "priority": Union[bool, int],
      "defend_against_air": bool,
      "defend_against_ground": bool,
      "attack_condition": Callable, # only if you intend for defend queen_control to turn offensive
      "attack_target": Point2, # used by offensive defence queen_control, otherwise not required
      "rally_point": Point2,
      "pass_own_threats": bool,
      "priority_defence_list": Set[UnitID]
  },
  "inject_queens": {
      "active": bool,
      "max": int,
      "priority": Union[bool, int],
      "defend_against_air": bool,
      "defend_against_ground": bool,
      "pass_own_threats": bool,
      "priority_defence_list": Set[UnitID]
    },
    # NOTE: Nydus Queens only become active when a Canal is placed on the map, so assign Nydus Queens to another role then set that role in `steal_from`.
  "nydus_queens": {
      "active": bool,
      "max": int,
      "priority": Union[bool, int],
      "defend_against_air": bool,
      "defend_against_ground": bool,
      "pass_own_threats": bool,
      "priority_defence_list": Set[UnitID],
      "attack_target": Point2,
      "nydus_move_function": Optional[Callable], # completely optional, nydus will still work without this
      "nydus_target": Point2, # not the nydus canal itself, but the target area we want to attack once out of the canal
      "steal_from": Set[QueenRoles], # found in `queens_sc2.consts`, should contain any of: QueenRoles.Creep, QueenRoles.Defence, QueenRoles.Inject
    },
}
```

However the library has sane defaults for missing values, this is a valid policy for example:
```python
async def on_start(self) -> None:
  early_game_queen_policy: Dict = {
    "creep_queens": {
        "active": True,
        "priority": True,
        "max": 4,
        "defend_against_ground": True,
    },
    "inject_queens": {"active": True, "priority": False, "max": 2},
  }
  
  self.queens = Queens(self, early_game_queen_policy)
```

You can pass new policies on the fly with the `set_new_policy` method:
```python
mid_game_queen_policy: Dict = {
    "creep_queens": {
        "max": 2,
        "priority": True,
        "defend_against_ground": False,
        "creep_style": "random",
    },
    "defence_queens": {
        "attack_condition": lambda: self.units(UnitID.QUEEN).amount > 30,
    },
    "inject_queens": {"active": False, "max": 0},
}
self.queens.set_new_policy(queen_policy=mid_game_queen_policy, reset_roles=True)
```

Attack target for offensive defence queens can be updated:
```python
self.queens.update_attack_target(self.enemy_start_locations[0])
```

Creep targets can also be updated with a new `List` of locations. (By default this is set to all expansion locations) Or if using Map Analyzer you can pass in a `List` of `Tuple`'s, where each `Tuple` contains a starting `Point2` and target `Point2`, `queens-sc2` will then try to creep along the ground path.
```python
# path should ideally contain no creep points
self.queens.update_creep_targets(path_to_third_base)
```

If using nyduses, make sure the nydus target is updated, this is not where the Nydus should be placed, rather the focal attack point from the Nydus itself:
```python
self.queens.update_nydus_target(self.enemy_start_locations[0])
```

### SC2 Map Analyzer support
`queens-sc2` comes with completely optional support for [SC2 Map Analyzer](https://github.com/eladyaniv01/SC2MapAnalysis), currently this allows for improved creep spread and better Queen control.

Example setup with MA (please follow instructions on the MA repo if needed):
```python
    from sc2 import BotAI
    from MapAnalyzer import MapData
    from queens_sc2.queens import Queens
    
    class ZergBot(BotAI):
        async def on_start(self) -> None:
            self.map_data = MapData(self)  # where self is your BotAI object from python-sc2
            self.queens = Queens(
                self, queen_policy=self.my_policy, map_data=self.map_data
            )
            
        async def on_step(self, iteration: int) -> None:
            ground_grid: np.ndarray = self.map_data.get_pyastar_grid()
            # you may want to add cost etc depending on your bot, 
            # depending on usecase it may not need a fresh grid every step
            await self.queens.manage_queens(iteration, grid=ground_grid)
```

### I only want creep spread
Check the example in `creep_example.py` which shows how to set a creep policy and manage separate groups of queens.

## Contributing
Pull requests are welcome, please submit an issue for feature requests or bug reports.
