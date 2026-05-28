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

tt.addInputField(x=1,
                 y=20,
                 width=30,
                 height=7,
                 name="NUMS",
                 visible=True,
                 prompt="Enter a number.\n>>> ",
                 borderStyle=Border.SINGLE_BOX)

# tt.stdout_FDI.setDefaultTarget(tt.tiles["TEST"].updateHeader)
tt.tiles["EVEN"].updateHeader("Even")
tt.tiles["ODD"].updateHeader("Odd")
tt.tiles["EVEN"].update(f"{tt.inputFields["NUMS"].inputMax}")
while True:
    i = int(tt.inputFields["NUMS"].getInput())
    if i % 2 == 0:
        tt.tiles["EVEN"].update(f"{i}")
    else:
        tt.tiles["ODD"].update(f"{i}")

tt.close()