from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.ttytiles.ttytiles import TerminalTiler

# Create terminal manager
tt = TerminalTiler()

# Create display
display = tt.addDisplayTile(
    x=(tt.cols - 45) // 2,
    y=(tt.rows - 14) // 2,
    width=45,
    height=14,
    borderStyle=TerminalTiler.Border.SINGLE_BOX,
    textWrap=TerminalTiler.Style.Wrap.WORD_WRAP,
)

# INTRO
display.set("Welcome to the DisplayTile demo.\n\nPress any key to continue.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# HEADERS
# Replace header
# This should be done when the DisplayTile is initialized, just doing this for dramatic effect
display.header.resize(1)
display.header.textJust=TerminalTiler.Style.Justify.CENTERED

# Update size to account for header, then redraw
display.resize()
display.drawBorder()

display.header.set("Headers")
display.set("DisplayTiles may have a header. The number of lines in the header can be specified when the element is created. By default, no header is added.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# SIZE MODE
display.header.set("Size Mode")
display.set("Size Mode may be set when the element is initialized. Available modes from TerminalTiler.Style.Size are:\n - FIXED\n - SCROLLING\nBy default, FIXED is used.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# FIXED
display.header.set("Size Mode: FIXED")
display.set("DisplayTile text disappears after scrolling off-screen.\n\n\n")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)
for i in range(10):
    display.update(f"Line {i + 1}")
    tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)
display.update(" \nPress ESC to continue.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ESCAPE)

# Change size mode
# Once again, this should be configured when the element is created.
display.sizeMode = TerminalTiler.Style.Size.SCROLLING
display.resize()
display.drawBorder()

# SCROLLING
display.header.set("Size Mode: SCROLLING")
display.set("DisplayTile text can be scrolled with the keyboard.\n\n\n")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)
for i in range(10):
    display.update(f"Line {i + 1}")
    tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)
display.update(" \nUse UP, DOWN, PG UP, and PG DN to navigate the text.\nPress ESC to continue.")
tt.focus(display)
tt.waitForKey(TerminalTiler.Keyboard.KEY_ESCAPE)
display.sizeMode = TerminalTiler.Style.Size.FIXED
display.resize()
display.drawBorder()

# JUSTIFICATION
display.header.set("Justification")
display.set("Text justification may be set for header and text buffers. Available modes from TerminalTiler.Style.Justify are:\n - LJUST\n - CENTERED\n - RJUST\nBy default, LJUST is used.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

display.header.textJust = TerminalTiler.Style.Justify.LJUST
display.textJust = TerminalTiler.Style.Justify.LJUST
display.header.set("Justification: LJUST")
display.set("Text justification may be set for header and text buffers. Available modes from TerminalTiler.Style.Justify are:\n - LJUST\n - CENTERED\n - RJUST\nBy default, LJUST is used.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

display.header.textJust = TerminalTiler.Style.Justify.CENTERED
display.textJust = TerminalTiler.Style.Justify.CENTERED
display.header.set("Justification: CENTERED")
display.set("Text justification may be set for header and text buffers. Available modes from TerminalTiler.Style.Justify are:\n - LJUST\n - CENTERED\n - RJUST\nBy default, LJUST is used.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

display.header.textJust = TerminalTiler.Style.Justify.RJUST
display.textJust = TerminalTiler.Style.Justify.RJUST
display.header.set("Justification: RJUST")
display.set("Text justification may be set for header and text buffers. Available modes from TerminalTiler.Style.Justify are:\n - LJUST\n - CENTERED\n - RJUST\nBy default, LJUST is used.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)
display.header.textJust = TerminalTiler.Style.Justify.CENTERED
display.textJust = TerminalTiler.Style.Justify.LJUST

# WRAPPING
display.header.set("Wrapping")
display.set("Text wrapping may be set for header and text buffers. Available modes from TerminalTiler.Style.Wrap are:\n - NOWRAP\n - WRAP\n - WORD_WRAP\nBy default, NOWRAP is used.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

display.textWrap = TerminalTiler.Style.Wrap.NOWRAP
display.header.set("Wrapping: NOWRAP")
display.set("NOWRAP - No text wrapping.\nWRAP - Text wrapping. Text is wrapped on the character at the end of the line.\nWORD_WRAP - Text wrapping. Text is wrapped on the last space before the end of the line.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

display.textWrap = TerminalTiler.Style.Wrap.WRAP
display.header.set("Wrapping: WRAP")
display.set("NOWRAP - No text wrapping.\nWRAP - Text wrapping. Text is wrapped on the character at the end of the line.\nWORD_WRAP - Text wrapping. Text is wrapped on the last space before the end of the line.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

display.textWrap = TerminalTiler.Style.Wrap.WORD_WRAP
display.header.set("Wrapping: WORD_WRAP")
display.set("NOWRAP - No text wrapping.\nWRAP - Text wrapping. Text is wrapped on the character at the end of the line.\nWORD_WRAP - Text wrapping. Text is wrapped on the last space before the end of the line.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# OUTRO
display.header.set("The End")
display.set("Press any key to continue.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# Close terminal manager
tt.close()