from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.ttytiles.ttytiles import TerminalTiler

# Create terminal manager
tt = TerminalTiler()

# Create display
display = tt.addDisplayTile(
    x=(tt.cols - 21) // 2,
    y=(tt.rows - 5) // 2,
    width=21,
    height=5,
    textJust=TerminalTiler.Style.Justify.CENTERED,
    borderStyle=TerminalTiler.Border.SINGLE_BOX
)

# Update text
display.update("\nHello World")

# Wait for keypress
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# Close terminal manager
tt.close()