from ttytiles import *
import time

tt = TerminalTiler()

tile_even = tt.addDisplayTile(x=1,
           y=1,
           width=tt.cols//2 - 1,
           height=10,
           textMode=DisplayTile.TEXT_NOWRAP,
           sizeMode=DisplayTile.SIZE_SCROLLING,
           borderStyle=Border.SINGLE_BOX,
           borderChar=None,
           headerLines=1,
           headerMode=Header.TEXT_NOWRAP,
           headerBorder=True)

tile_odd = tt.addDisplayTile(x=tt.cols//2,
           y=1,
           width=tt.cols//2 - 1,
           height=10,
           textMode=DisplayTile.TEXT_NOWRAP,
           sizeMode=DisplayTile.SIZE_FIXED,
           borderStyle=Border.SINGLE_BOX,
           borderChar=None,
           headerLines=1,
           headerMode=Header.TEXT_NOWRAP,
           headerBorder=True)

std_out = tt.addDisplayTile(x=tt.cols//2,
          y=15,
          width=tt.cols//2 - 1,
          height=10,
          textMode=DisplayTile.TEXT_WRAP,
          sizeMode=DisplayTile.SIZE_SCROLLING,
          borderStyle=Border.DOUBLE_BOX)

tt.stdout_FDI.setDefaultTarget(std_out.update)

input_1 = tt.addInputTile(x=1,
                 y=20,
                 width=40,
                 height=5,
                 visible=True,
                 prompt="Enter a number.\n>>> ",
                 borderStyle=Border.HEAVY_BOX)

tile_even.updateHeader("Even Numbers")
tile_odd.updateHeader("Odd Numbers")

tile_even.colors["BORDER_FG_F"] = (0, 120, 250)
tile_odd.colors["BORDER_FG_F"] = (250, 120, 0)
input_1.colors["BORDER_FG_F"] = (120, 250, 0)

tile_even.colors["TEXT_FG_F"] = (0, 0, 250)
tile_odd.colors["TEXT_FG_F"] = (250, 0, 0)
input_1.colors["TEXT_FG_F"] = (0, 250, 0)

for i in range(10):
    tile_even.update(f"{i*2}")

while tt.isAlive():
    i = int(input_1.getInput())
    if i % 2 == 0:
        tile_even.update(f"{i}")
    else:
        tile_odd.update(f"{i}")

tt.close()