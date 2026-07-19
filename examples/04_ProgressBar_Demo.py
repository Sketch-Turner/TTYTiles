from ttytiles import TerminalTiler

# Worker to simulate progress bar updates
import time
def worker(update):
    for _ in range(200):
        update()
        time.sleep(2 * 60 / 200)

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

# Create progressbar
progress = tt.addProgressBar(
    x=10,
    y=display.y + display.height + 2,
    width=tt.cols - 20,
    barChar='█',
    textLeft="|",
    textRight="|",
    max=200
)
# INTRO
display.set("Welcome to the ProgressBar demo.\n\nPress any key to continue.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# BAR
# Simulate work
progress.show()
import threading
threading.Thread(target=worker, args=(progress.update,), daemon=True).start()

display.set("The bar must be assigned a char or string that will be drawn to show progression.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# LEFT TEXT
display.set("ProgressBar allows customization of formatted strings to the left and right of the bar as well as overlayed on top.")
progress.textLeft = "{VALUE}/{MAX} |"
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# OVERLAY TEXT
display.set("Format values include:\n\nVALUE   - Current value\nMAX     - Max value\nPERCENT - Completion as a percent\nRATIO   - Completion as a decimal")
progress.textOverlay = "{PERCENT}%"
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# RIGHT TEXT
display.set("A timer is started when the element is shown and used to calculate time-based format values:\n\nAVG_ITTS  - Iterations per second\nAVG_TIME  - Seconds per iteration\nELAPSED   - Seconds since start\nREMAINING - Estimated seconds remaining")
progress.textRight = "| Avg: {AVG_TIME:S.mmm} Rem: {REMAINING}"
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# FORMATTING
display.set("AVG_TIME, ELAPSED, and REMAINING are formatted MM:SS by default.\nCustom formats may be provided using:\n\nH - Hours\nM - Minutes\nS - Seconds\nm - Milliseconds")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)
progress.hide()

# OUTRO
display.set("The End.\n\nPress any key to continue.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# Close terminal manager
tt.close()