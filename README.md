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
Use `TerminalTiler()` to start the terminal manager. The screen will be cleared, the cursor will be hidden, and stdout will be hooked.

### DisplayTile
Useful for displaying text. Optional header. Optional scrollbar. Text wrapping and justification options. See example `01_DisplayTile_Demo`.
Header and text buffer color. Border style and color. See example `TODO`.

### InputTile
Use for reading user input. Input length is bounded by the InputTile object. Optional prompt. See example `02_InputTile_Demo`.
Prompt and input text color. Border style and color. See example `TODO`.

### Table

### ProgressBar

### MessageBox

### Alert

## Examples
### 00_Hello_World
Displays text in a DisplayTile, then exits after the user presses a key.
### 01_DisplayTile_Demo
Describes DisplayTile attributes and usage.
### 02_InputTile_Demo
Describes InputTile attributes and usage.
### 03_Table_Demo
Describes Table attributes and usage.
### 04_ProgressBar_Demo
Describes ProgressBar attributes and usage.
### 05_MessageBox_Demo
Describes MessageBox attributes and usage.
### 06_Alert_Demo
Describes Alert attributes and usage.

## Issues
Report issues to sketch.turner.dev+ttytiles@gmail.com