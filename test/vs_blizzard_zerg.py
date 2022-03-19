import random
import sys
from os import path

sys.path.append(path.join(path.dirname(__file__), ".."))

import sc2
from sc2 import Race, Difficulty
from sc2.player import Bot, Computer

from examples.example import ZergBot

bot = Bot(Race.Zerg, ZergBot())

# Start game
if __name__ == "__main__":
    random_map = random.choice(
        [
            "2000AtmospheresAIE",
            "BlackburnAIE",
            "JagannathaAIE",
            "LightshadeAIE",
            "OxideAIE",
            "RomanticideAIE",
        ]
    )
    sc2.run_game(
        sc2.maps.get(random_map),
        [
            bot,
            Computer(Race.Zerg, Difficulty.Easy),
        ],
        realtime=False,
    )
