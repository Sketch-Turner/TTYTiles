from ttytiles import *

tt = TerminalTiler()
tt.clearScreen()
tt.hide_cursor()

tt.addTile(x=1,
           y=1,
           width=tt.cols//2 - 1,
           height=10,
           name="EVEN",
           textMode=Tile.TEXT_NOWRAP,
           borderStyle=Border.SINGLE_BOX,
           borderChar=None,
           headerLines=1,
           headerMode=Header.TEXT_NOWRAP,
           headerBorder=True)

tt.addTile(x=tt.cols//2,
           y=1,
           width=tt.cols//2 - 1,
           height=10,
           name="ODD",
           textMode=Tile.TEXT_NOWRAP,
           borderStyle=Border.SINGLE_BOX,
           borderChar=None,
           headerLines=1,
           headerMode=Header.TEXT_NOWRAP,
           headerBorder=True)

# tt.stdout_FDI.setDefaultTarget(tt.tiles["TEST"].updateHeader)
tt.tiles["EVEN"].updateHeader("Even")
tt.tiles["ODD"].updateHeader("Odd")

while True:
    i = int(input(">"))
    if i % 2 == 0:
        tt.tiles["EVEN"].update(f"{i}")
    else:
        tt.tiles["ODD"].update(f"{i}")


tt.close()