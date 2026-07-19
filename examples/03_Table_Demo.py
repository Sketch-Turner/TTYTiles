from ttytiles import TerminalTiler

# Create terminal manager
tt = TerminalTiler()

# Create display
display = tt.addDisplayTile(
    x=(tt.cols - 45) // 2,
    y=(tt.rows - 15) // 2,
    width=45,
    height=10,
    borderStyle=TerminalTiler.Border.SINGLE_BOX,
    textWrap=TerminalTiler.Style.Wrap.WORD_WRAP,
    canFocus=False
)

# Create table
table = tt.addTable(
    x = (tt.cols - 60) // 2,
    y = (tt.rows - 10) // 2,
    width=60,
    height=15,
    headerLines=1,
    headerTextJust=TerminalTiler.Style.Justify.CENTERED,
    borderStyle=TerminalTiler.Border.SINGLE_BOX
)

# INTRO
display.set("Welcome to the Table demo.\n\nPress any key to continue.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# FORMATTING
display.hide()
display.y -= 5
display.resize(height=5)
display.show()
display.set("Tables have the same header, text justification and text wrapping options as DisplayTiles.")

table.header.set("Example Table")
table.load([
    ["Label 1", "Label 2", "Label 3"],
    ["Data A", "Data D", "Data G"],
    ["Data B", "Data E", "Data H"],
    ["Data C", "Data F", "Data I"]
])
table.row_list[0].setTextJust(TerminalTiler.Style.Justify.CENTERED)
table.show()
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# LAYOUT
display.set("Table space is divided evenly among rows and columns. Row and column size may also be customized.")
table.row_list[0].size = 1
table.col_list[0].size -= 6
table.col_list[1].size += 12
table.show()
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# OVERFLOW
display.set("If the size of all rows or columns is less than the table space, the last row or column will expand.")
table.col_list[0].size = 7
table.col_list[1].size = 7
table.show()
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

display.set("If the size of all rows or columns is greater than the table space, rows or columns may be truncated.")
table.row_list[0].size = 1
table.col_list[0].size = 39
table.col_list[1].size = 19
table.show()
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# OUTRO
table.hide()
display.hide()
display.y += 5
display.resize(height=10)
display.show()
display.set("The End.\n\nPress any key to continue.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# Close terminal manager
tt.close()