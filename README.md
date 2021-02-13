# queens-sc2
queens-sc2 is a small customizable library to aid development of sc2 zerg bots developed with [python-sc2](https://github.com/BurnySc2/python-sc2). A challenge when developing zerg bots is effective queen management since queens have various roles including injecting, creep and defence. 
queens-sc2 was created to allow zerg authors to rapidly develop a bot without being encumbered by queen management. The main idea of queens-sc2 is the author creates a policy which the library reads and handles appropriately.

## Prerequisites 
It is expected the user has already installed [python-sc2](https://github.com/BurnySc2/python-sc2), the only other library used in this project is [numpy](https://numpy.org/).

## Getting started
Clone or download this repository and put the `queens_sc2` directory in your bot folder like so:
```
MyBot
└───queens_sc2
│   └───queens_sc2 library files
└───your bot files and directories
```

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
        # call the queen library to handle our queens
        await self.queens.manage_queens(iteration)
        
        # can optionally pass in a custom selection of queens, ie:
        # queens: Units = self.units.tags_in(self.sc2_queen_tags)
        # await self.queens.manage_queens(iteration, queens)
        # if not the library will manage all queens automatically
        
        
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
      "distance_between_existing_tumors": int,
      "should_tumors_block_expansions": bool,
      "creep_targets": List[Point2], # library will cycle through these locations
      "spread_style": str, # "targeted" is default, or "random"
      "rally_point": Point2,
      "first_tumor_position": Optional[Point2],
      "prioritize_creep": Callable, # prioritize over defending bases if energy is available?
      "pass_own_threats": bool, # if set to True, library wont calculate enemy near bases, you should pass air and ground threats to manage_queens() method
      "priority_defence_list", set[UnitID] # queens will prioritise defending these unit types over all other jobs
  },
  "defence_queens": {
      "active": bool,
      "max": int,
      "priority": Union[bool, int],
      "defend_against_air": bool,
      "defend_against_ground": bool,
      "attack_condition": Callable, # only if you intend for defend queens to turn offensive
      "attack_target": Point2, # used by offensive defence queens, otherwise not required
      "rally_point": Point2,
      "pass_own_threats": bool,
      "priority_defence_list", set[UnitID]
  },
  "inject_queens": {
      "active": bool,
      "max": int,
      "priority": Union[bool, int],
      "defend_against_air": bool,
      "defend_against_ground": bool,
      "pass_own_threats": bool,
      "priority_defence_list", set[UnitID]
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

Creep targets can also be updated with a new `List` of locations. (By default this is set to all expansion locations)
```python
# path should ideally contain no creep points
self.queens.update_creep_targets(path_to_third_base)
```

### I only want creep spread
Check the example in `creep_example.py` which shows how to set a creep policy and manage seperate groups of queens.

## Contributing
Pull requests are welcome, please submit an issue for feature requests or bug reports.
