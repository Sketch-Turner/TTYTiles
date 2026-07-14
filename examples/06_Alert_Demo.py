from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.ttytiles.ttytiles import TerminalTiler

# Create terminal manager
tt = TerminalTiler()

# Create display
display = tt.addDisplayTile(
    x=(tt.cols - 44) // 2,
    y=(tt.rows - 15) // 2,
    width=44,
    height=10,
    borderStyle=TerminalTiler.Border.SINGLE_BOX,
    textWrap=TerminalTiler.Style.Wrap.WORD_WRAP,
    canFocus=False
)

alert = tt.addAlert(
    x=(tt.cols - 30) // 2,
    y=display.y + 5,
    width=30,
    height=9,
    text = "Alert!\n\nPress any key to continue.",
    textJust=TerminalTiler.Style.Justify.CENTERED,
    textWrap=TerminalTiler.Style.Wrap.WORD_WRAP,
    borderStyle=TerminalTiler.Border.SINGLE_BOX
)

# INTRO
display.update("Welcome to the Alert demo.\n\nPress any key to continue.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)
display.clear()

# KEYPRESS
display.update("The Alert is a popup that is drawn over all other elements.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)
alert.show(-1)
display.clear()

# TIME
display.update("Alerts may be configure to close with a specific keypress, any keypress, or after a certain time has passed.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)
alert.text = "3 second Alert!"
alert.show(3)
display.clear()

# OUTRO
display.update("The End.\n\nPress any key to continue.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# Close terminal manager
tt.close()