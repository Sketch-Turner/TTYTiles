# TTYTiles

Python library for creating customizable terminal user interfaces. Provides tools for creating, positioning, and managing interactive UI elements with configurable borders, colors, text wrapping, and justification.

Supports user input through `InputTile` and terminal output through `DisplayTile`, `Table`, `ProgressBar`, `MessageBox`, and `Alert` components.

![Demo](/img/demo.gif)

## Contents
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
  - [TerminalTiler](#terminaltiler)
  - [DisplayTile](#displaytile)
  - [InputTile](#inputtile)
  - [Table](#table)
  - [ProgressBar](#progressbar)
  - [MessageBox](#messagebox)
  - [Alert](#alert)
- [Examples](#examples)
- [Issues](#issues)

## Requirements
Python >=3.10

## Installation
```bash
pip install TTYTiles
```

## Usage
Start the UI manager by initializing a `TerminalTiler()` object. Create the desired elements. Once complete, use `close()` to restore the terminal environment.

```python
import ttytiles

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
display.set("\nHello World")

# Wait for keypress
tt.waitForKey(TerminalTiler.Keyboard.KEY_ANY)

# Close terminal manager
tt.close()
```

### TerminalTiler

`TerminalTiler` manages the terminal UI lifecycle, including keyboard input, rendering, focus management, popup handling, and synchronized output from multiple threads.

Creating a `TerminalTiler` instance initializes the terminal for interactive use by:

- Switching the Windows console to UTF-8 (Windows only).
- Determining the current terminal dimensions.
- Clearing the terminal screen.
- Hiding the terminal cursor.
- Installing an `FDInterceptor` on `stdout` to synchronize terminal output.
- Starting the keyboard listener.
- Initializing the internal tile registry.

```python
tt = TerminalTiler()
```

#### Creating Elements

All interface elements are created through `TerminalTiler` factory methods.

| Method | Description |
|--------|-------------|
| `addDisplayTile(...)` | Create a read-only text display. |
| `addInputTile(...)` | Create a text input field. |
| `addTable(...)` | Create a table widget. |
| `addProgressBar(...)` | Create a progress bar. |
| `addMessageBox(...)` | Create a modal dialog with selectable buttons. |
| `addAlert(...)` | Create a modal alert popup. |

Each method validates that the element fits within the terminal before it is created.

#### Borders

Borders define the appearance of an element's outline. A border may use one of the built-in styles or a custom character set. Border styles, colors, and focused variants may be specified when the element is created.

| Constructor | Description |
|--------------|-------------|
| `borderStyle` | Border style (`NO_BORDER`, `SINGLE_BOX`, `DOUBLE_BOX`, `HEAVY_BOX`, `ASCII`, `HEAVY_ASCII`) |
| `borderChar` | Custom border character set. Overrides `borderStyle`. |
| `borderStyleFocused` | Border style while focused. Defaults to `borderStyle`. |
| `borderCharFocused` | Custom focused border character set. Overrides `borderStyleFocused`. |
| `borderFG` | Border foreground color |
| `borderBG` | Border background color |
| `borderFG_F` | Focused border foreground color |
| `borderBG_F` | Focused border background color |

##### Built-in Styles

TerminalTiler includes the following predefined border styles:

| Character | SINGLE_BOX | DOUBLE_BOX | HEAVY_BOX | ASCII | HEAVY_ASCII |
|-------|--------------|--------------|--------------|---------|---------------|
| lineH | `─` | `═` | `━` | `-` | `=` |
| lineV | `│` | `║` | `┃` | `\|` | `\|` |
| cornerNW | `┌` | `╔` | `┏` | `+` | `*` |
| cornerNE | `┐` | `╗` | `┓` | `+` | `*` |
| cornerSW | `└` | `╚` | `┗` | `+` | `*` |
| cornerSE | `┘` | `╝` | `┛` | `+` | `*` |
| junctionVE | `├` | `╠` | `┣` | `+` | `*` |
| junctionVW | `┤` | `╣` | `┫` | `+` | `*` |
| junctionHS | `┬` | `╦` | `┳` | `+` | `*` |
| junctionHN | `┴` | `╩` | `┻` | `+` | `*` |
| junctionAll | `┼` | `╬` | `╋` | `+` | `*` |
| boxLower | `▄` | `▄` | `▄` | `#` | `#` |
| boxUpper | `▀` | `▀` | `▀` | `#` | `#` |
| boxFull | `█` | `█` | `█` | `#` | `#` |
| arrowUp | `▲` | `▲` | `▲` | `^` | `^` |
| arrowDown | `▼` | `▼` | `▼` | `v` | `v` |
| arrowLeft | `⯇` | `⯇` | `⯇` | `<` | `<` |
| arrowRight | `⯈` | `⯈` | `⯈` | `>` | `>` |

```python
display = tt.addDisplayTile(
    ...,
    borderStyle=TerminalTiler.Border.SINGLE_BOX,
    borderStyleFocused=TerminalTiler.Border.DOUBLE_BOX
)
```

##### Custom Character Sets

A custom border style may be created by supplying `borderChar`. The provided string defines the complete set of characters used by the border renderer.

The character set is automatically adjusted to exactly 18 characters:
- If the string is shorter than 18 characters, it is repeated until the limit has been reached.
- If the string is longer than 18 characters, it is truncated.

| Index | Purpose |
|-------|---------|
| 0 | Horizontal line |
| 1 | Vertical line |
| 2 | Northwest corner |
| 3 | Northeast corner |
| 4 | Southwest corner |
| 5 | Southeast corner |
| 6 | Vertical junction with connection to the east |
| 7 | Vertical junction with connection to the west |
| 8 | Horizontal junction with connection to the south |
| 9 | Horizontal junction with connection to the north |
| 10 | Four-way junction |
| 11 | Lower half block |
| 12 | Upper half block |
| 13 | Full block |
| 14 | Up arrow |
| 15 | Down arrow |
| 16 | Left arrow |
| 17 | Right arrow |

Example:

```python
# Custom border identical to TerminalTiler.Border.SINGLE_BOX
display = tt.addDisplayTile(
    ...,
    borderStyle=TerminalTiler.Border.CUSTOM,
    borderChar="─│┌┐└┘├┤┬┴┼▄▀█▲▼⯇⯈"
)

# Custom border using a single character.
# The character is repeated to fill all 18 drawing primitives.
display = tt.addDisplayTile(
    ...,
    borderStyle=TerminalTiler.Border.CUSTOM,
    borderChar="*"
)
```

##### Border Merging

When two bordered elements overlap, their borders are automatically merged if all of the following are true:

- They use compatible border character sets.
- Their foreground colors are identical.
- Their background colors are identical.

Otherwise, each border is drawn independently.

```python
left = tt.addDisplayTile(
    ...,
    borderStyle=TerminalTiler.Border.SINGLE_BOX
)

right = tt.addDisplayTile(
    ...,
    borderStyle=TerminalTiler.Border.SINGLE_BOX
)
```

Changing either the border style or border colors prevents merging.

#### Focus Management

Keyboard input is sent only to the currently focused element.

Focus may be changed programmatically:

```python
tt.focus(element)
```

or by pressing **Tab** to cycle through focusable elements.

Elements with `canFocus=False` are skipped during navigation.  

Focus may be removed from the current element:
```python
tt.focus(None)
```

#### Keyboard Input

`TerminalTiler` provides helper methods for waiting on keyboard events.

| Method | Description |
|--------|-------------|
| `waitForKey(key)` | Block until the specified key is pressed. |
| `isAlive()` | Returns `False` after the terminal manager has been closed. |

Use `TerminalTiler.Keyboard.KEY_ANY` to wait for any key.

#### Redirecting stdout

`TerminalTiler` intercepts `stdout` and exposes the `FDInterceptor` through `tt.stdout_FDI`.

The interceptor can forward every line written to `stdout` to a callback function, allowing terminal output from your application or third-party libraries to be displayed inside a `DisplayTile`.

Assign a callback using:

```python
tt.stdout_FDI.setDefaultTarget(display.update)
```

After a callback is registered, anything written to `stdout` is automatically appended to the display:

```python
tt.stdout_FDI.default_target = displayTile.update

print("Program started.")
print("Loading configuration...")
```

This also works for libraries that write to `stdout` using `print()` internally.  
This provides a simple way to redirect logs, status messages, and console output into a `DisplayTile` without modifying the code that produces the output.

By default, intercepted output is discarded unless a target callback has been configured.

To disable redirection at any time, clear the callback:

```python
tt.stdout_FDI.setDefaultTarget(None)
```

Subsequent writes to `stdout` will continue to be intercepted but will no longer be forwarded.

#### Closing

When finished, call:

```python
tt.close()
```

This:

- Stops the keyboard listener.
- Restores the terminal cursor.
- Releases the stdout interceptor.
- Wakes any threads waiting for keyboard input.
- Leaves the cursor below the rendered interface.

### DisplayTile
A `DisplayTile` is a read-only text display widget for presenting formatted output, logs, help text, or status information.

Features include:

- Optional multi-line header.
- Optional vertical scrollbar (enabled automatically in scrolling mode).
- Configurable text wrapping and justification for both the header and text buffer.
- Fixed or scrollable text buffers.
- Runtime updates without recreating the widget.
- Independently configurable border style, border colors, and text colors.

See example `01_DisplayTile_Demo`.

#### Updating

DisplayTiles support three methods for modifying displayed content:

| Method | Description |
|--------|-------------|
| `set(text)` | Replace all existing text with the provided content. Clears the current buffer before adding the new text. |
| `update(text)` | Append text to the existing buffer. Text is formatted according to the current size, justification, and wrap settings. |
| `clear()` | Remove all text from the display buffer. |

Example:

```python
# Replace existing content
display.set("Loading...")

# Append additional content
display.update("Complete.")

# Remove all content
display.clear()
```

The header uses the same interface:

```python
# Replace header text
display.header.set("Title")

# Append header text
display.header.update("- Subtitle -")

# Clear the header
display.header.clear()
```

#### Size Modes
`DisplayTile` supports two size modes from `TerminalTiler.Style.Size`:

| Mode | Description |
|------|-------------|
| `FIXED` | Displays only the visible portion of the buffer. Older lines are discarded once they scroll off-screen. |
| `SCROLLING` | Retains the entire text buffer and allows navigation using the keyboard. A scrollbar is displayed when necessary. |

#### Keyboard Controls
When using `SCROLLING` mode and the widget has focus, the following keys are available:

| Key | Action |
|-----|--------|
| ↑ | Scroll up one line |
| ↓ | Scroll down one line |
| PgUp | Scroll up one page |
| PgDn | Scroll down one page |
| Home | Jump to beginning |
| End | Jump to end |

#### Text Wrapping
Text wrapping is controlled independently for the header and text buffer using `TerminalTiler.Style.Wrap`.

Available modes:

| Mode | Description |
|------|-------------|
| `NOWRAP` | Lines are displayed exactly as written. Characters beyond the visible width are clipped. |
| `WRAP` | Wraps at the widget width, splitting words when necessary. |
| `WORD_WRAP` | Wraps at the last whitespace before the widget edge whenever possible. |

#### Text Justification
Header and text buffers may use different justification modes.

| Mode | Description |
|------|-------------|
| `LJUST` | Left-aligns text within the available width. |
| `CENTERED` | Centers text within the available width. |
| `RJUST` | Right-aligns text within the available width. |

#### Colors

DisplayTiles support independent colors for the text, border, and header, each with optional focused variants. Colors may be specified when the tile is created using `addDisplayTile()` or changed later using `setColor()`.

Each color is an RGB tuple of the form `(R, G, B)`. Passing `None` to `setColor()` resets all colors to their defaults.

| Constructor | `setColor()` Key | Description |
|--------------|------------------|-------------|
| `colorFG` | `TEXT_FG` | Text foreground |
| `colorBG` | `TEXT_BG` | Text background |
| `colorFG_F` | `TEXT_FG_F` | Focused text foreground |
| `colorBG_F` | `TEXT_BG_F` | Focused text background |
| `borderFG` | `BORDER_FG` | Border foreground |
| `borderBG` | `BORDER_BG` | Border background |
| `borderFG_F` | `BORDER_FG_F` | Focused border foreground |
| `borderBG_F` | `BORDER_BG_F` | Focused border background |
| `headerFG` | `HEADER_FG` | Header foreground |
| `headerBG` | `HEADER_BG` | Header background |
| `headerFG_F` | `HEADER_FG_F` | Focused header foreground |
| `headerBG_F` | `HEADER_BG_F` | Focused header background |

```python
# Constructor
display = tt.addDisplayTile(
    ...,
    colorFG=(100, 149, 237),
    borderFG=(0, 70, 180),
    headerFG=(173, 216, 255)
)

# Update later
display.setColor({
    "TEXT_FG": (100, 149, 237),
    "BORDER_FG": (0, 70, 180),
    "HEADER_FG": (173, 216, 255)
})

# Reset all colors
display.setColor(None)
```

### InputTile
An `InputTile` is an editable text input widget for collecting keyboard input from the user. It supports cursor navigation, optional prompts, focus management, and multiple simultaneous input fields.

Features include:

- Single or multi-line text input.
- Optional inline prompt.
- Independently configurable border style, border colors, and text colors.

See example `02_InputTile_Demo`.

#### Prompt

An optional prompt may be displayed before the editable text.

The prompt:

- Is specified during creation using `prompt=...` or later with `setPrompt()`.
- Occupies part of the available width on the first line.
- Does not count as editable text.
- Remains fixed while the user edits their input.

#### Input Length

Input is constrained by the visible area of the widget.

- Characters automatically wrap onto additional lines.
- Input cannot extend beyond the widget boundaries.
- Additional characters are ignored once the available space is full.

#### Reading Input
Input is retrieved using:

```python
text = inputTile.getInput()
```

`getInput()` blocks until the user presses **Enter**, then returns the submitted string and clears the input field.

Only the currently focused `InputTile` receives keyboard input.  
Focus may be changed with:

- `tt.focus(tile)`
- The **Tab** key (when multiple focusable elements exist)

#### Keyboard Controls

| Key | Action |
|-----|--------|
| ← | Move cursor left |
| → | Move cursor right |
| Home | Move cursor to beginning |
| End | Move cursor to end |
| Backspace | Delete previous character |
| Delete | Delete character under cursor |
| Enter | Submit the current input |
| Esc | Clear the current input |
| Tab | Move focus to the next focusable element |

#### Colors

InputTiles support independent colors for the prompt, input text, and border, each with optional focused variants. Colors may be specified when the tile is created using `addInputTile()` or changed later using `setColor()`.

Each color is an RGB tuple of the form `(R, G, B)`. Passing `None` to `setColor()` resets all colors to their defaults.

| Constructor | `setColor()` Key | Description |
|--------------|------------------|-------------|
| `promptFG` | `PROMPT_FG` | Prompt foreground |
| `promptBG` | `PROMPT_BG` | Prompt background |
| `promptFG_F` | `PROMPT_FG_F` | Focused prompt foreground |
| `promptBG_F` | `PROMPT_BG_F` | Focused prompt background |
| `inputFG` | `INPUT_FG` | Input foreground |
| `inputBG` | `INPUT_BG` | Input background |
| `inputFG_F` | `INPUT_FG_F` | Focused input foreground |
| `inputBG_F` | `INPUT_BG_F` | Focused input background |
| `borderFG` | `BORDER_FG` | Border foreground |
| `borderBG` | `BORDER_BG` | Border background |
| `borderFG_F` | `BORDER_FG_F` | Focused border foreground |
| `borderBG_F` | `BORDER_BG_F` | Focused border background |

```python
# Constructor
input = tt.addInputTile(
    ...,
    promptFG=(173, 216, 255),
    inputFG=(100, 149, 237),
    borderFG=(0, 70, 180)
)

# Update later
input.setColor({
    "PROMPT_FG": (173, 216, 255),
    "INPUT_FG": (100, 149, 237),
    "BORDER_FG": (0, 70, 180)
})

# Reset all colors
input.setColor(None)
```

### Table

A `Table` displays structured data arranged into rows and columns. It provides configurable cell sizing, optional headers, and independent formatting for headers, rows, columns, and individual cells.

Features include:

- Optional multi-line header.
- Configurable row and column sizes.
- Per-cell, per-row, and per-column formatting.
- Runtime updates without recreating the table.
- Independently configurable border style, border colors, header colors, and cell colors.

See example `03_Table_Demo`.

#### Cell Access

Cells may be modified individually or through their containing rows and columns.

| Expression | Description |
|------------|-------------|
| `table.cells[row][col]` | Access an individual cell. |
| `table.row_list[row]` | Access a row object. |
| `table.col_list[col]` | Access a column object. |

Each `Cell`, row, and column exposes formatting and content methods:

| Method | Description |
|--------|-------------|
| `set(text)` | Replace the current text content. |
| `update(text)` | Append text to the current content. |
| `clear()` | Remove the current text content. |
| `setColor(colors)` | Update text colors. |
| `setTextWrap(mode)` | Change the text wrapping mode. |
| `setTextJust(mode)` | Change the text justification mode. |

Example:

```python
# Replace a cell's content
table.cells[0][0].set("Data A")

# Append to a cell's content
table.cells[0][0].update("Data B")

# Clear a cell
table.cells[0][0].clear()
```

Calling a formatting method on a row or column automatically applies the change to every cell it contains.

#### Loading Data

Populate a table using:

```python
table.load(data)
```

where `data` is a two-dimensional list.

Example:

```python
table.load([
    ["Name", "Age"],
    ["Alice", "24"],
    ["Bob", "31"]
])
```
#### Row and Column Layout

By default, available space is divided evenly among all rows and columns.

Individual sizes may be modified through:

- `table.row_list[i].size`
- `table.col_list[i].size`

Layout behavior:

- If the total requested size is **smaller** than the available table space, the final row or column expands to fill the remaining space.
- If the total requested size is **larger** than the available table space, rows or columns are truncated to fit within the table.

#### Colors

Tables support independent colors for the cell text, border, and header, each with optional focused variants. Colors may be specified when the table is created using `addTable()` or changed later using `setColor()`.

Each color is an RGB tuple of the form `(R, G, B)`. Passing `None` to `setColor()` resets all colors to their defaults.

| Constructor | `setColor()` Key | Description |
|--------------|------------------|-------------|
| `colorFG` | `TEXT_FG` | Default cell foreground |
| `colorBG` | `TEXT_BG` | Default cell background |
| `colorFG_F` | `TEXT_FG_F` | Default focused cell foreground |
| `colorBG_F` | `TEXT_BG_F` | Default focused cell background |
| `borderFG` | `BORDER_FG` | Border foreground |
| `borderBG` | `BORDER_BG` | Border background |
| `borderFG_F` | `BORDER_FG_F` | Focused border foreground |
| `borderBG_F` | `BORDER_BG_F` | Focused border background |
| `headerFG` | `HEADER_FG` | Header foreground |
| `headerBG` | `HEADER_BG` | Header background |
| `headerFG_F` | `HEADER_FG_F` | Focused header foreground |
| `headerBG_F` | `HEADER_BG_F` | Focused header background |

```python
# Constructor
table = tt.addTable(
    ...,
    colorFG=(100, 149, 237),
    borderFG=(0, 70, 180),
    headerFG=(173, 216, 255)
)

# Update later
table.setColor({
    "TEXT_FG": (100, 149, 237),
    "BORDER_FG": (0, 70, 180),
    "HEADER_FG": (173, 216, 255)
})

# Reset all colors
table.setColor(None)
```

Individual rows, columns, and cells can also be colored independently.

```python
# Entire row
table.rows[0].setColor({
    "TEXT_FG": (255, 0, 0)
})

# Entire column
table.cols[1].setColor({
    "TEXT_FG": (0, 180, 255)
})

# Individual cell
table.cells[2][3].setColor({
    "TEXT_FG": (0, 255, 0)
})
```

### ProgressBar

A `ProgressBar` displays the completion status of a task using a horizontal bar with optional formatted text positioned to the left, right, or overlaid on the bar.

Features include:

- Customizable fill character or string.
- Left, right, and overlay text.
- Dynamic placeholder formatting.
- Automatic elapsed time and ETA calculations.
- Independently configurable border style and colors.
- Independently configurable bar colors.

See example `04_ProgressBar_Demo`.

#### Progress Range

Progress is tracked between `0` and `max`.

Update the current value using:

```python
progress.update(increment)
```

Each call increments the current value by `increment`. Default is `1`.

#### Bar Appearance

The filled portion of the bar is drawn using the value supplied by:

```python
barChar="█"
```

Any character or string may be used.

Additional text may be displayed:

- To the left of the bar (`textLeft`)
- On top of the bar (`textOverlay`)
- To the right of the bar (`textRight`)

#### Format Placeholders

Text fields support the following placeholders:

| Placeholder | Description |
|------------|-------------|
| `{VALUE}` | Current progress value. |
| `{MAX}` | Maximum progress value. |
| `{PERCENT}` | Progress percentage (0–100). |
| `{RATIO}` | Progress ratio (0.0–1.0). |
| `{AVG_ITTS}` | Average iterations per second. |
| `{AVG_TIME}` | Average time per iteration. |
| `{ELAPSED}` | Time elapsed since the progress bar was shown. |
| `{REMAINING}` | Estimated time remaining. |

#### Time Formatting

When `show()` is called, the progress bar starts an internal timer used to compute elapsed time, averages, and the estimated remaining time.

Time placeholders default to `MM:SS` formatting but may be customized using format specifiers.

Example:

```text
{AVG_TIME:S.mmm}
```

Supported specifiers:

| Specifier | Description |
|-----------|-------------|
| `H` | Hours |
| `HH` | Zero-padded hours |
| `M` | Minutes |
| `MM` | Zero-padded minutes |
| `S` | Seconds |
| `SS` | Zero-padded seconds |
| `m` | Tenths of a second |
| `mm` | Hundredths of a second |
| `mmm` | Milliseconds |

#### Colors

ProgressBars support independent colors for the bar text and border. Colors may be specified when the bar is created using `addProgressBar()` or changed later using `setColor()`.

Each color is an RGB tuple of the form `(R, G, B)`. Passing `None` to `setColor()` resets all colors to their defaults.

| Constructor | `setColor()` Key | Description |
|--------------|------------------|-------------|
| `colorFG` | `TEXT_FG` | Progress bar foreground |
| `colorBG` | `TEXT_BG` | Progress bar background |
| `borderFG` | `BORDER_FG` | Border foreground |
| `borderBG` | `BORDER_BG` | Border background |

```python
# Constructor
progress = tt.addProgressBar(
    ...,
    colorFG=(100, 149, 237),
    borderFG=(0, 70, 180)
)

# Update later
progress.setColor({
    "TEXT_FG": (100, 149, 237),
    "BORDER_FG": (0, 70, 180)
})

# Reset all colors
progress.setColor(None)
```

### MessageBox

A `MessageBox` is a modal popup used to display information and collect a button selection from the user. It is rendered above all other elements and temporarily captures keyboard focus until a button is activated.

Features include:

- Modal popup window.
- Optional multi-line header.
- Configurable message text.
- One or more selectable buttons.
- Keyboard navigation and hotkeys.
- Returns a value associated with the selected button.
- Independently configurable border style, border colors, and text colors.

See example `05_MessageBox_Demo`.

#### Modal Behavior

A `MessageBox` is always drawn above other terminal elements.

When shown:

- The message box receives keyboard focus.
- Navigation is restricted to its buttons.
- The message box remains visible until a button is activated.

A `MessageBox` will only render if at least one button has been added.

#### Buttons

Buttons are added using:

```python
messagebox.addButton(...)
```

Each button must define a value and may define a hotkey.  
When a button is activated, the message box returns the button's associated value.

#### Keyboard Controls

| Key | Action |
|-----|--------|
| Tab | Select the next button. |
| Enter | Activate the selected button. |
| Hotkey | Activate the associated button immediately. |

#### Hotkeys

Buttons may define an optional keyboard shortcut.

Example:

```python
messagebox.addButton(
    text="Yes",
    value=True,
    hotkey="y",
    ...
)
```

Pressing **Y** immediately activates the button and returns its associated value.

#### Colors

MessageBoxes support independent colors for the message text, border, and buttons. Colors may be specified when the MessageBox and its buttons are created or changed later using `setColor()`.

Each color is an RGB tuple of the form `(R, G, B)`. Passing `None` to `setColor()` resets all colors to their defaults.

| Constructor | `setColor()` Key | Description |
|--------------|------------------|-------------|
| `colorFG` | `TEXT_FG` | Message text foreground |
| `colorBG` | `TEXT_BG` | Message text background |
| `borderFG` | `BORDER_FG` | MessageBox border foreground |
| `borderBG` | `BORDER_BG` | MessageBox border background |
| Button `colorFG` | `BUTTON_TEXT_FG` | Button text foreground |
| Button `colorBG` | `BUTTON_TEXT_BG` | Button text background |
| Button `colorFG_F` | `BUTTON_TEXT_FG_F` | Focused button text foreground |
| Button `colorBG_F` | `BUTTON_TEXT_BG_F` | Focused button text background |
| Button `borderFG` | `BUTTON_BORDER_FG` | Button border foreground |
| Button `borderBG` | `BUTTON_BORDER_BG` | Button border background |
| Button `borderFG_F` | `BUTTON_BORDER_FG_F` | Focused button border foreground |
| Button `borderBG_F` | `BUTTON_BORDER_BG_F` | Focused button border background |

```python
# Constructor
msg = tt.addMessageBox(
    ...,
    colorFG=(255, 255, 255),
    borderFG=(0, 70, 180)
)

msg.addButton(
    ...,
    colorFG=(255, 255, 255),
    borderFG=(0, 120, 255)
)

# Update later
msg.setColor({
    "TEXT_FG": (255, 255, 255),
    "BORDER_FG": (0, 70, 180),

    "BUTTON_TEXT_FG": (255, 255, 255),
    "BUTTON_BORDER_FG": (0, 120, 255)
})

# Reset all colors
msg.setColor(None)
```

### Alert

An `Alert` is a modal popup used to temporarily display a message. It is rendered above all other elements and automatically closes after a specified timeout or in response to keyboard input.

Features include:

- Modal popup window.
- Configurable message text.
- Optional timeout.
- Dismiss by any key or a specific key.
- Independently configurable border style, border colors, and text colors.

See example `06_Alert_Demo`.

#### Modal Behavior

An `Alert` is always drawn above other terminal elements.

When displayed:

- The alert receives keyboard focus.
- It remains visible until its dismissal condition is met.

#### Dismissal Modes

Alerts are displayed using:

```python
alert.show(duration, close_key)
```

| Parameters | Behavior |
|------------|----------|
| `duration < 0`, `close_key=None` | Wait until **any key** is pressed. |
| `duration < 0`, `close_key=<key>` | Wait until the specified `TerminalTiler.Keyboard` key is pressed. |
| `duration > 0`, `close_key=None` | Display the alert for the specified number of seconds. |
| `duration > 0`, `close_key=<key>` | Display the alert until the specified key is pressed or the specified number of seconds has passed. |

Examples:

```python
# Wait for any key
alert.show(-1)

# Wait for Escape
alert.show(-1, TerminalTiler.Keyboard.KEY_ESCAPE)

# Close after 3 seconds
alert.show(3)

# Close after 3 seconds or when Escape is pressed
alert.show(3, TerminalTiler.Keyboard.KEY_ESCAPE)
```

#### Colors

Alerts support independent colors for the text and border. Colors may be specified when the alert is created using `addAlert()` or changed later using `setColor()`.

Each color is an RGB tuple of the form `(R, G, B)`. Passing `None` to `setColor()` resets all colors to their defaults.

| Constructor | `setColor()` Key | Description |
|--------------|------------------|-------------|
| `colorFG` | `TEXT_FG` | Alert foreground |
| `colorBG` | `TEXT_BG` | Alert background |
| `borderFG` | `BORDER_FG` | Border foreground |
| `borderBG` | `BORDER_BG` | Border background |

```python
# Constructor
alert = tt.addAlert(
    ...,
    colorFG=(255, 255, 255),
    borderFG=(220, 53, 69)
)

# Update later
alert.setColor({
    "TEXT_FG": (255, 255, 255),
    "BORDER_FG": (220, 53, 69)
})

# Reset all colors
alert.setColor(None)
```

## Examples

### 00_Hello_World
Displays text in a DisplayTile, then exits after the user presses a key.

### 01_DisplayTile_Demo
Demonstrates `DisplayTile` creation, headers, size modes, text wrapping, justification, and scrolling.

### 02_InputTile_Demo
Demonstrates `InputTile` creation, prompts, keyboard input, focus management, and multiple simultaneous input fields.

### 03_Table_Demo
Demonstrates loading tabular data, header configuration, row and column sizing, and cell formatting.

### 04_ProgressBar_Demo
Demonstrates progress tracking, formatted text placeholders, elapsed time, ETA calculations, and custom time formatting.

### 05_MessageBox_Demo
Demonstrates modal dialogs, button creation, keyboard navigation, hotkeys, and returning button values.

### 06_Alert_Demo
Demonstrates modal alerts with automatic timeout and keyboard-based dismissal.

### 07_Color_Demo
Demonstrates built-in foreground/background RGB color support.

### 08_Border_Demo
Showcases the available border styles and how adjacent borders automatically merge.

### 09_Simple_IO
Demonstrates basic terminal input and output using `InputField` and `DisplayTile`.

### 10_Port_Scanner
A simple multithreaded port scanner demonstrating live terminal updates, progress tracking, and interactive UI components.

### 11_ProgressBar_TQDM
When I grow up, I want to be just like TQDM.

### 12_L33T_Dashboard
An animated terminal dashboard showcasing the capabilities of TTYTiles.

## Issues

Report issues to sketch.turner.dev+ttytiles@gmail.com.

Please include:

- **TTYTiles version**
- **Python version**
- **Operating system**
- **Terminal emulator** (Windows Terminal, cmd.exe, PowerShell, GNOME Terminal, etc.)
- **Minimal reproducible example**
- **Expected behavior**
- **Actual behavior**
- **Full traceback or error message** (if applicable)
- **Screenshots or terminal output** (if applicable)