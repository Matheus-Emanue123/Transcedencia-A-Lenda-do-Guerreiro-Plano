"""
TRANSCENDÊNCIA - A Lenda do Cavaleiro Plano
Trabalho final de Computação Gráfica - CEFET-MG

Execute:  python main.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.core import Game          # noqa: E402
from scenes import menu               # noqa: E402


def main():
    game = Game()
    if '--demo' in sys.argv:
        from engine.autoplay import Driver
        game.driver = Driver(game)
        game.run(lambda g: menu.Menu(g))
        return
    # permite pular direto para uma fase:  python main.py 4
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        from scenes import PHASES
        i = max(1, min(len(PHASES), int(sys.argv[1]))) - 1
        game.run(lambda g: PHASES[i](g))
    else:
        game.run(lambda g: menu.Menu(g))


if __name__ == '__main__':
    main()
