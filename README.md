# queens-sc2
queens-sc2 is a small customizable library to aid development of sc2 zerg bots developed with [python-sc2](https://github.com/BurnySc2/python-sc2). A challenge when developing zerg bots is effective queen management since queens have various roles including injecting, creep and defence. 
queens-sc2 was created to allow zerg authors to rapidly develop a bot without being encumbered by queen management. The main idea of queens-sc2 is the author creates a policy which the library reads and handles appropriately.

## Prerequisites 
It is expected the user has already installed [python-sc2](https://github.com/BurnySc2/python-sc2), the only other library used in this project is [numpy](https://numpy.org/) https://numpy.org/.

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
      "max_queens": int,
      "priority": bool,
      "defend_against_air": bool,
      "defend_against_ground": bool,
      "distance_between_existing_tumors": int,
      "should_tumors_block_expansions": bool,
      "creep_targets": List[Point2],
      "spread_style": str, # "targeted" is default, or "random"
      "rally_point": Point2
  },
  "defence_queens": {
      "active": bool,
      "max_queens": int,
      "priority": bool,
      "defend_against_air": bool,
      "defend_against_ground": bool,
      "attack_condition": Callable,
      "attack_target": Point2,
      "rally_point": Point2
  },
  "inject_queens": {
      "active": bool,
      "max_queens": int,
      "priority": bool,
      "defend_against_air": bool,
      "defend_against_ground": bool,},
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
  
  self.queens = Queens(self, **early_game_queen_policy)
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
self.queens.set_new_policy(reset_roles=True, **mid_game_queen_policy)
```

### I only want creep spread
Check the example in `creep_example.py` which shows how to set a creep policy and manage seperate groups of queens.

## Caveat
Defence queen logic is generalized and should work well enough up to a certain level. However, the logic as to manage extra queens can be subjective depending on playstyle. A bot at an advanced level should write their own code for excess queens and perhaps then just set a policy for creep and inject queens.

## Contributing
Pull requests are welcome, please submit an issue for feature requests or bug reports.
