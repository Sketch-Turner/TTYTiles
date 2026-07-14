# TTYTiles
Python library for managing terminal UI elements. Allows creation and positioning of customizable elements. Provides configuration of border, color, text wrapping, and text justification. User input can be captured using the InputTile element. Output can be displayed via OutputTile, Table, ProgressBar, MessageBox, or Alert elements. 

gif

## Contents
Requirements
Installation
Usage
Examples
Issues

## Requirements
Python >=3.10

## Installation
pip install TTYTiles

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
display.update("\nHello World")

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

#### Focus Management

Keyboard input is sent only to the currently focused element.

Focus may be changed programmatically:

```python
tt.focus(element)
```

or by pressing **Tab** to cycle through focusable elements.

Elements with `canFocus=False` are skipped during navigation.

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

#### Output
One or more threads can update the DisplayTile in realtime using:

```python
displayTile.updateHeader("Text")
displayTile.update("Text")
```

The text is appended and formatted according to the size, justification and wrap settings.

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

Each `Cell`, row, and column exposes formatting methods:

| Method | Description |
|--------|-------------|
| `update(text)` | Replace the cell's text. (Cell only) |
| `setColor(colors)` | Update text colors. |
| `setTextWrap(mode)` | Change the text wrapping mode. |
| `setTextJust(mode)` | Change the text justification mode. |

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
    hotkey="y"
)
```

Pressing **Y** immediately activates the button and returns its associated value.

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
|-----------|----------|
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

### 08_Border_Demo

### 09_Simple_IO

### 10_Port_Scanner

### 11_ProgressBar_TQDM

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