from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.ttytiles.ttytiles import TerminalTiler

# Create terminal manager
tt = TerminalTiler()

# Create display
display1 = tt.addDisplayTile(
    x=(tt.cols - 47) // 2,
    y=(tt.rows - 12) // 2,
    width=47,
    height=12,
    borderStyle=TerminalTiler.Border.SINGLE_BOX,
    textWrap=TerminalTiler.Style.Wrap.WORD_WRAP
)

display2 = tt.addDisplayTile(
    x=(display1.x + (display1.width // 2)) - 1,
    y=display1.y + 3,
    width=display1.width // 2,
    height=display1.height,
    visible=False,
    borderStyle=TerminalTiler.Border.SINGLE_BOX,
    textWrap=TerminalTiler.Style.Wrap.WORD_WRAP,
)

# INTRO
display1.set("Welcome to the Border demo.\n\nPress any key to continue.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# TYPES
display1.border.charset = TerminalTiler.Border.Charset(None)
display1.drawBorder()
display1.set("By default no border is present.\n\nText will still be bounded by the element and will wrap accordingly.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

display1.border.charset = TerminalTiler.Border.Charset(r"##/\\/")
display1.drawBorder()
display1.set(" To declare a custom border charset, provide  a string containing the desired drawing      characters. Each position is mapped to a     specific UI element such as lines, corners,  and junctions.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

display1.border.charset = TerminalTiler.Border.Charset(TerminalTiler.Border.BORDER_CHARS[TerminalTiler.Border.SINGLE_BOX])
display1.drawBorder()
display1.set("Built-in border styles include:\n")
display1.update(" ┌────────────┐ ╔════════════╗ ┏━━━━━━━━━━━┓")
display1.update(" │ SINGLE_BOX │ ║ DOUBLE_BOX ║ ┃ HEAVY_BOX ┃")
display1.update(" └────────────┘ ╚════════════╝ ┗━━━━━━━━━━━┛\n")
display1.update("          +-------+ *=============*")
display1.update("          | ASCII | | HEAVY_ASCII |")
display1.update("          +-------+ *=============*")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# MERGING
display1.hide()
display1.clear()
display1.resize(width=display1.width//2)
display1.show()
display1.set("If the borders of two elements overlap, they may be merged.")

display2.show()
display2.set("If the border style, foreground color, and background color are the same, the borders will be merged.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

display2.border.charset = TerminalTiler.Border.Charset(TerminalTiler.Border.BORDER_CHARS[TerminalTiler.Border.HEAVY_BOX])
display2.drawBorder()
display2.set("If the style or colors do not match, the borders will not be merged.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# OUTRO
display2.hide()
display1.resize(width=display1.width*2)
display1.show()
display1.set("The End.\n\nPress any key to continue.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# Close terminal manager
tt.close()