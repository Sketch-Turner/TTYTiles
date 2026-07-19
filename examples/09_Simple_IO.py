from ttytiles import TerminalTiler

# Initialize TerminalTiler.
tt = TerminalTiler()


# Display tile for even numbers.
tile_even = tt.addDisplayTile(
    x=1,
    y=1,
    width=tt.cols//2 - 1,
    height=12,
    textWrap=TerminalTiler.Style.Wrap.WRAP,
    sizeMode=TerminalTiler.Style.Size.SCROLLING,

    # Normal and focused border styles.
    borderStyle=TerminalTiler.Border.SINGLE_BOX,
    borderStyleFocused=TerminalTiler.Border.HEAVY_BOX,

    # Focused border color
    borderFG_F=(0, 170, 255),

    # Center the header text.
    headerLines=1,
    headerTextJust=TerminalTiler.Style.Justify.CENTERED
)


# Display tile for odd numbers.
tile_odd = tt.addDisplayTile(
    x=tt.cols//2,
    y=1,
    width=tt.cols//2 - 1,
    height=12,
    textWrap=TerminalTiler.Style.Wrap.WRAP,
    sizeMode=TerminalTiler.Style.Size.SCROLLING,

    # Normal and focused border styles.
    borderStyle=TerminalTiler.Border.SINGLE_BOX,
    borderStyleFocused=TerminalTiler.Border.HEAVY_BOX,

    # Focused border color
    borderFG_F=(255, 120, 0),

    # Center the header text.
    headerLines=1,
    headerTextJust=TerminalTiler.Style.Justify.CENTERED
)


# Input field used to enter numbers.
input = tt.addInputTile(
    x=1,
    y=tile_even.y + tile_even.height + 4,
    width=40,
    height=5,

    # Prompt displayed before user input.
    prompt="Enter a number.\n>>> ",

    # Normal and focused border styles.
    borderStyle=TerminalTiler.Border.SINGLE_BOX,
    borderStyleFocused=TerminalTiler.Border.HEAVY_BOX,

    # Prompt and input text colors.
    promptFG_F=(255, 200, 0),
    inputFG_F=(180, 150, 80)
)


# Alert popup used for invalid input messages.
alert = tt.addAlert(
    x=(tt.cols - 30) // 2,
    y=(tt.rows - 10) // 2,
    width=30,
    height=10,

    # Center alert text and wrap long messages.
    textJust=TerminalTiler.Style.Justify.CENTERED,
    textWrap=TerminalTiler.Style.Wrap.WORD_WRAP,

    # Red border to indicate an error.
    borderStyle=TerminalTiler.Border.SINGLE_BOX,
    borderFG=(255, 0, 0)
)


# Set display headers.
tile_even.header.set("Even Numbers")
tile_odd.header.set("Odd Numbers")


# Start with the input tile selected.
tt.focus(input)


# Main application loop.
while tt.isAlive():
    # Wait for user input.
    val = input.getInput()

    # Process numeric input.
    if val.isnumeric():
        i = int(val)

        # Display even numbers in the left tile.
        if i % 2 == 0:
            tile_even.update(f"{i}")

        # Display odd numbers in the right tile.
        else:
            tile_odd.update(f"{i}")

    # Empty input exits the application.
    elif val == "":
        break

    # Show an error popup for invalid input.
    else:
        alert.text = f'Invalid Input:\n\n{val}\n\nInput must be a number!'
        alert.show(-1)


# Shutdown TerminalTiler cleanly.
tt.close()