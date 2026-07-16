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

# Create messagebox
messagebox = tt.addMessageBox(
    x=(tt.cols - 30) // 2,
    y=display.y + 5,
    width=30,
    height=11,
    text = "Use TAB to select.\nUse ENTER to submit.",
    headerLines=1,
    headerText="MessageBox Demo",
    headerTextJust=TerminalTiler.Style.Justify.CENTERED,
    textWrap=TerminalTiler.Style.Wrap.WORD_WRAP,
    borderStyle=TerminalTiler.Border.SINGLE_BOX
)

# Add buttons
messagebox.addButton(
    value=None,
    width=10,
    height=3,
    text="Continue",
    textJust=TerminalTiler.Style.Justify.CENTERED,
    borderStyle=TerminalTiler.Border.SINGLE_BOX,
    borderStyleFocused=TerminalTiler.Border.HEAVY_BOX
)
# INTRO
display.set("Welcome to the MessageBox demo.\n\nPress any key to continue.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# CONTROLS
display.set("The MessageBox is a popup that is drawn over all other elements. It will only render if one or more buttons are configured.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)
messagebox.show()

# HOTKEY
display.set("MessageBox buttons can be assigned a hotkey. When the hotkey is pressed or the button is selected, the MessageBox returns the value of the button.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

messagebox.buttons[0].width = 9
messagebox.buttons[0].text = "(A)lpha"
messagebox.buttons[0].hotkey = 'a'
messagebox.addButton(
    value=None,
    width=9,
    height=3,
    text="(B)ravo",
    hotkey='b',
    textJust=TerminalTiler.Style.Justify.CENTERED,
    borderStyle=TerminalTiler.Border.SINGLE_BOX,
    borderStyleFocused=TerminalTiler.Border.HEAVY_BOX
)
messagebox.show()

# OUTRO
display.set("The End.\n\nPress any key to continue.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# Close terminal manager
tt.close()