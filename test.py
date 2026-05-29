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
                 width=20,
                 height=5,
                 name="NUMS",
                 visible=True,
                 prompt="Enter a number.\n>>> ",
                 borderStyle=Border.SINGLE_BOX)

# tt.stdout_FDI.setDefaultTarget(tt.tiles["TEST"].updateHeader)
tt.tiles["EVEN"].updateHeader("Even")
tt.tiles["ODD"].updateHeader("Odd")
f = tt.inputFields["NUMS"]
tt.tiles["ODD"].update(f"{f.inputMax} = ({f.rows} - {len(f.prompt)}) * {f.cols} + ({f.cols} - ({f.px} - {f.tx}))")
# tt.tiles["ODD"].update("┌─┐ ┌─┐ ┏━┓ ┏━┓ ┏▄┓ ┃█┃\n│▲│ │▼│ ┃▲┃ ┃▼┃  ▀\n└─┘ └─┘ ┗━┛ ┗━┛     ↕")
while True:
    i = int(tt.inputFields["NUMS"].getInput())
    if i % 2 == 0:
        tt.tiles["EVEN"].update(f"{i}")
    else:
        tt.tiles["ODD"].update(f"{i}")

tt.close()