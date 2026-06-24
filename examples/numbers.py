from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ttytiles import TerminalTiler

tt = TerminalTiler()

tile_even = tt.addDisplayTile(x=1,
                              y=1,
                              width=tt.cols//2 - 1,
                              height=10,
                              textMode=TerminalTiler.DisplayTile.TEXT_NOWRAP,
                              sizeMode=TerminalTiler.DisplayTile.SIZE_SCROLLING,
                              borderStyle=TerminalTiler.Border.SINGLE_BOX,
                              borderChar=None,
                              headerLines=1,
                              headerMode=TerminalTiler.Header.TEXT_NOWRAP,
                              headerBorder=True)

tile_odd = tt.addDisplayTile(x=tt.cols//2,
                             y=1,
                             width=tt.cols//2 - 1,
                             height=10,
                             textMode=TerminalTiler.DisplayTile.TEXT_NOWRAP,
                             sizeMode=TerminalTiler.DisplayTile.SIZE_SCROLLING,
                             borderStyle=TerminalTiler.Border.SINGLE_BOX,
                             borderChar=None,
                             headerLines=1,
                             headerMode=TerminalTiler.Header.TEXT_NOWRAP,
                             headerBorder=True)

input_1 = tt.addInputTile(x=1,
                          y=20,
                          width=40,
                          height=5,
                          visible=True,
                          prompt="Enter a number.\n>>> ",
                          borderStyle=TerminalTiler.Border.HEAVY_BOX)

tile_even.updateHeader("Even Numbers")
tile_odd.updateHeader("Odd Numbers")

tile_even.colors["BORDER_FG_F"] = (0, 120, 250)
tile_odd.colors["BORDER_FG_F"] = (250, 120, 0)
input_1.colors["BORDER_FG_F"] = (120, 250, 0)

tile_even.colors["TEXT_FG_F"] = (0, 0, 250)
tile_odd.colors["TEXT_FG_F"] = (250, 0, 0)
input_1.colors["TEXT_FG_F"] = (0, 250, 0)

while tt.isAlive():
    val = input_1.getInput()
    if val.isnumeric():
        i = int(val)
        if i % 2 == 0:
            tile_even.update(f"{i}")
        else:
            tile_odd.update(f"{i}")
    else:
        break

tt.close()