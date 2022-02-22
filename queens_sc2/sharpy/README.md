# sharpy-sc2 integration

## Prerequisites 
It is expected the user has already installed [sharpy-sc2](https://github.com/DrInfy/sharpy-sc2).  
See [Chance](https://github.com/lladdy/chance-sc2) for a working example of this integration.

## Getting started
If you're starting from scratch, try the example bot.

### Initialize the QueensSc2 manager
To integrate into an existing sharpy bot, initialize an instance of `QueensSc2Manager` in your bot's `configure_managers` method.

You can pass an initial policy like so:
```python
    def configure_managers(self) -> Optional[List["ManagerBase"]]:
        queen_policy = {
            # policy here
        }
        return [QueensSc2Manager(queen_policy)]
```

This is all that is required for queens-sc2 to function.

### Policy setting
You can use `SetQueensSc2Policy` in your sharpy build order to set the policy during the game.  
```python
    async def create_plan(self) -> BuildOrder:
        # in case you need access to the manager...
        queens_manager = self.knowledge.get_manager(QueensSc2Manager)

        early_game_queen_policy = {
            # define your early game policy here
        }

        mid_game_queen_policy = {
            # define your early game policy here
        }
        
        return BuildOrder(
            SetQueensSc2Policy(early_game_queen_policy, policy_name="early_game_queen_policy"),
            
            # Early game build here...
            
            SetQueensSc2Policy(mid_game_queen_policy, policy_name="mid_game_queen_policy"),
            
            # Mid game build here...
        )
```

Alternatively, you can also set the policy via the manager by calling `queens_manager.set_new_policy(queen_policy)`.

## Example bot
See [sharpysc2_example.py](../../examples/sharpysc2_example.py) for an example of using this integration.
