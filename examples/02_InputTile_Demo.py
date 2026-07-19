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

# Create input tile
input1 = tt.addInputTile(
    x=display.x,
    y=display.y + display.height + 1,
    width=display.width,
    height=3,
    visible=False,
    borderStyle=TerminalTiler.Border.SINGLE_BOX,
    borderStyleFocused=TerminalTiler.Border.HEAVY_BOX
)

input2 = tt.addInputTile(
    x=display.x + 1 + (display.width - 1) // 2,
    y=display.y + display.height + 1,
    width=(display.width - 1) // 2,
    height=3,
    visible=False,
    prompt=">",
    borderStyle=TerminalTiler.Border.SINGLE_BOX,
    borderStyleFocused=TerminalTiler.Border.HEAVY_BOX
)

# INTRO
display.set("Welcome to the InputTile demo.\n \nPress any key to continue.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# CONTROLS
display.set("Use LEFT, RIGHT, HOME, and END to control the cursor. Use ESC to clear the current input.\n \nType 'next' to continue.")
input1.show()
tt.focus(input1)

# Loop while TerminalTiler is active, prevents the code from being stuck the loop if the TerminalTiler is closed.
while tt.isAlive():
    s = input1.getInput()
    if s:
        if s.upper() == "NEXT":
            break

# PROMPT
display.set("An inline prompt may be specified when the element is initialized. Input automatically wraps to empty lines but cannot exceed the borders of the InputTile.\n \nType 'next' to continue.")
input1.hide()
input1.resize(height=5)
input1.setPrompt("Prompt: ")
input1.show()
tt.focus(input1)

while tt.isAlive():
    s = input1.getInput()
    if s:
        if s.upper() == "NEXT":
            break

# MULTIPLE
display.set("Keyboard input will be sent to the focused element. This allows multiple InputTiles to be active at once. Use TAB to switch between elements.\n\nType 'next' to continue.")
input1.hide()
input1.resize(width=(display.width - 1) // 2, height=3)
input1.setPrompt(">")
input2.show()
input1.show()
tt.focus(input1)

# Each InputTile will be monitored by a separate thread.
import threading
import queue

results = queue.Queue()
threading.Thread(target=lambda: [results.put(s) for _ in iter(int, 1) if tt.isAlive() for s in [input1.getInput()] if s], daemon=True).start()
threading.Thread(target=lambda: [results.put(s) for _ in iter(int, 1) if tt.isAlive() for s in [input2.getInput()] if s], daemon=True).start()

while tt.isAlive():
    try:
        s = results.get(timeout=0.1)
        if s.upper() == "NEXT":
            break

    except queue.Empty:
        pass

# OUTRO
input1.hide()
input2.hide()
display.set("The End.\n\nPress any key to continue.")
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# Close terminal manager
tt.close()