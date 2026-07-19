from ttytiles import TerminalTiler

# Create terminal manager
tt = TerminalTiler()

# Create display
display = tt.addDisplayTile(
    x=(tt.cols - 45) // 2,
    y=(tt.rows - 18) // 2,
    width=45,
    height=14,
    borderStyle=TerminalTiler.Border.SINGLE_BOX,
    textWrap=TerminalTiler.Style.Wrap.WORD_WRAP
)

# Create input tile
input = tt.addInputTile(
    x=display.x,
    y=display.y + display.height + 1,
    width=display.width,
    height=3,
    visible=False,
    prompt="Prompt: ",
    borderStyle=TerminalTiler.Border.SINGLE_BOX
)

# Create table
table = tt.addTable(
    x = (tt.cols - 33) // 2,
    y = (tt.rows - 23) // 2 + 9,
    width=33,
    height=17,
    borderStyle=TerminalTiler.Border.SINGLE_BOX,
    canFocus=True
)

# INTRO
display.set("Welcome to the Color demo.\n\nPress any key to continue.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# FG
display.header.resize(1)
display.header.textJust = TerminalTiler.Style.Justify.CENTERED
display.resize()
display.drawBorder()
display.header.set("Color Demo")
display.set("Each element has components that may be assigned custom RGB foreground and background colors if the terminal supports it.\n\nFor DisplayTiles these include:")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

display.update(" - Header")
display.setColor({"HEADER_FG":(173, 216, 255),"HEADER_FG_F":(255, 138, 101)})
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

display.update(" - Text")
display.setColor({"TEXT_FG":(100, 149, 237),"TEXT_FG_F":(244, 81, 30)})
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

display.update(" - Border")
display.setColor({"BORDER_FG":(0, 70, 180),"BORDER_FG_F":(211, 47, 47)})
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

display.set("Alternate colors can be defined for when the element is focused.\n\nPress TAB to change focus.\nPress ESC to continue.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ESCAPE)

# INPUT
display.header.resize(0)
display.resize()
display.setColor()
tt.focus(None)
input.show()
display.canFocus = False
display.show()
display.set("InputTiles offer slightly different color customization:\n")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

display.update(" - Prompt")
input.setColor({"PROMPT_FG":(173, 216, 255),"PROMPT_FG_F":(255, 138, 101)})
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

display.update(" - Input")
input.setColor({"INPUT_FG":(100, 149, 237),"INPUT_FG_F":(244, 81, 30)})
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

display.update(" - Border")
input.setColor({"BORDER_FG":(0, 70, 180),"BORDER_FG_F":(211, 47, 47)})
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

display.set("Alternate colors can be defined for when the element is focused.\n\nPress TAB to change focus.\nType 'next' to continue.")
while tt.isAlive():
    s = input.getInput()
    if s:
        if s.upper() == "NEXT":
            break

input.canFocus = False
input.hide()
tt.focus(None)

# TABLE
display.hide()
display.y -= 2
display.resize(height=7)
display.show()
display.set("Tables have the same color configuration options as DisplayTiles.\nIndividual customization of each row, col, or cell is also available.")

table.load([["" for j in range(8)] for i in range(8)])
table.show()
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

colors = [
    (255, 0, 0),      # Red
    (255, 255, 0),    # Yellow
    (0, 255, 0),      # Green
    (0, 255, 255),    # Cyan
    (0, 0, 255),      # Blue
    (255, 0, 255),    # Magenta
]

steps = table.table_rows + table.table_cols - 2

for i in range(table.table_rows):
    for j in range(table.table_cols):
        t = (i + j) / max(1, steps)

        pos = t * (len(colors) - 1)
        idx = int(pos)
        frac = pos - idx

        if idx >= len(colors) - 1:
            color = colors[-1]
        else:
            a = colors[idx]
            b = colors[idx + 1]

            color = (
                int(a[0] + (b[0] - a[0]) * frac),
                int(a[1] + (b[1] - a[1]) * frac),
                int(a[2] + (b[2] - a[2]) * frac)
            )

        table.cells[i][j].update("▐█▌")
        table.cells[i][j].setColor({"TEXT_FG": color})

tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# OUTRO
table.hide()
display.hide()
display.y += 2
display.resize(height=10)
display.show()
display.set("The End.\n\nPress any key to continue.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# Close terminal manager
tt.close()