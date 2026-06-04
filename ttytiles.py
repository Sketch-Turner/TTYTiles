import os
import sys
import threading
from collections import deque
import queue

if os.name == "nt":
    import msvcrt
else:
    import tty
    import termios
    import select


class Keyboard:
    """
    Small cross-platform keyboard handler for terminal UIs.
    """
    KEY_UP = "UP"
    KEY_DOWN = "DOWN"
    KEY_LEFT = "LEFT"
    KEY_RIGHT = "RIGHT"
    KEY_BACKSPACE = "BACKSPACE"
    KEY_DELETE = "DELETE"
    KEY_ENTER = "ENTER"
    KEY_ESCAPE = "ESCAPE"
    KEY_END = "END"
    KEY_HOME = "HOME"
    KEY_TAB = "TAB"
    PRINTABLE = set([chr(c) for c in range(32, 127)])

    def __init__(self):
        """
        Initialize the keyboard input handler.
        """
        self.keystrokes = queue.Queue()
        self.keyMap = {}

    def getKey(self)->str:
        """
        Blocking call that retrieves the next key press from the input queue.

        Returns:
            str: The next available key from the keystrokes queue.
        """
        return self.keystrokes.get()

    def start(self):
        """
        Starts the background keyboard reader thread.
        """
        threading.Thread(target=self._read, daemon=True).start()

    def mapKey(self, key:str, func):
        """
        Register a callback function for a specific key.
        Function is passed the triggering key when called.

        Args:
            key (str): The key identifier.
            func (callable): Function to execute when the key is pressed.
        """
        self.keyMap[key] = func

    def _read(self):
        """
        Internal keyboard polling loop.

        Continuously reads raw key input and dispatches it to a mapped
        handler if one exists. Otherwise, the key is queued for later use.
        """
        while True:
            k = self._readKey()
            func = self.keyMap.get(k, None)
            if not func is None:
                func(k)
            else:
                self.keystrokes.put(k)

    def _readKey(self)->str:
        """
        Cross-platform key press handler.
        """
        if os.name == "nt":
            ch = msvcrt.getwch()

            # special keys
            if ch in ("\x00", "\xe0"):
                code = msvcrt.getwch()

                return {
                    "H": Keyboard.KEY_UP,
                    "P": Keyboard.KEY_DOWN,
                    "K": Keyboard.KEY_LEFT,
                    "M": Keyboard.KEY_RIGHT,
                    "S": Keyboard.KEY_DELETE,
                    "G": Keyboard.KEY_HOME,
                    "O": Keyboard.KEY_END,
                }.get(code, code)

            if ch == "\r":
                return Keyboard.KEY_ENTER

            if ch == "\t":
                return Keyboard.KEY_TAB

            if ch == "\x08":
                return Keyboard.KEY_BACKSPACE

            if ch == "\x1b":
                return Keyboard.KEY_ESCAPE

            return ch

        else:
            fd = sys.stdin.fileno()

            old = termios.tcgetattr(fd)

            try:
                tty.setcbreak(fd)

                ch = sys.stdin.read(1)

                if ch == "\x1b":
                    # possible escape sequence
                    r, _, _ = select.select([sys.stdin], [], [], 0.01)

                    if r:
                        seq = sys.stdin.read(2)

                        # delete: ESC [ 3 ~
                        if seq == "[3":
                            if select.select([sys.stdin], [], [], 0.01)[0]:
                                sys.stdin.read(1)  # consume ~
                            return Keyboard.KEY_DELETE

                        # home: ESC [ H
                        if seq == "[H":
                            return Keyboard.KEY_HOME

                        # end: ESC [ F
                        if seq == "[F":
                            return Keyboard.KEY_END

                        return {
                            "[A": Keyboard.KEY_UP,
                            "[B": Keyboard.KEY_DOWN,
                            "[D": Keyboard.KEY_LEFT,
                            "[C": Keyboard.KEY_RIGHT,
                        }.get(seq, Keyboard.KEY_ESCAPE)

                    return Keyboard.KEY_ESCAPE

                if ch in ("\r", "\n"):
                    return Keyboard.KEY_ENTER

                if ch == "\x09":
                    return Keyboard.KEY_TAB

                if ch in ("\x7f", "\b"):
                    return Keyboard.KEY_BACKSPACE

                return ch

            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)

    @staticmethod
    def isPrintable(s:str)->bool:
        """
        Checks whether a character is printable.

        Args:
            s (str): Single character to test.

        Returns:
            bool: True if character is in the printable ASCII range, otherwise False.
        """
        return s in Keyboard.PRINTABLE

class FDInterceptor:
    """
    Intercepts writes to a file descriptor using an OS pipe and forwards captured 
    output lines to a user-defined callback function in a background thread.
    """
    def __init__(self, fd):
        """
        Redirects the specified file descriptor into an internal pipe,
        starts a relay thread, and captures all future output written
        to the descriptor.

        Args:
            fd (int): File descriptor to intercept (Currently only supports STDIN).
        """
        self.default_target = None
        self.fd = fd
        self._running = True

        self.r, self.w = os.pipe()
        self.real_fd = os.dup(fd)

        os.dup2(self.w, fd)
        os.close(self.w)

        if fd == 1:
            sys.stdout = os.fdopen(fd, "w", buffering=1)

        self.thread = threading.Thread(target=self.relay, daemon=True)
        self.thread.start()

    def relay(self):
        """
        Continuously reads intercepted output from the pipe and forwards
        decoded lines to the configured callback function until the
        interceptor is stopped or the pipe is closed.
        """
        try:
            while self._running:
                try:
                    data = os.read(self.r, 65536)
                except OSError:
                    break

                if not data:
                    break

                if self.default_target is not None:
                    for line in data.splitlines(True):
                        self.default_target(line.decode("utf-8", errors="replace").strip())
        finally:
            pass

    def setDefaultTarget(self, func):
        """
        Sets the callback function that receives intercepted output lines.

        Args:
            func (callable): Function accepting a single string argument.
        """
        self.default_target = func

    def close(self):
        """
        Stops interception, restores the original file descriptor,
        closes internal pipe resources, and waits for the relay
        thread to terminate.
        """
        self._running = False

        # wake up os.read() by closing WRITE side
        try:
            os.close(self.fd)
        except OSError:
            pass

        # close read end
        try:
            os.close(self.r)
        except OSError:
            pass

        # restore original fd
        try:
            os.dup2(self.real_fd, self.fd)
            os.close(self.real_fd)
        except OSError:
            pass

        # wait for thread exit
        if self.thread.is_alive():
            self.thread.join()

class Header:
    """
    Stores and manages a fixed-size collection of text lines for
    terminal-style header rendering, with optional text wrapping
    and border support.
    """
    TEXT_NOWRAP = 0
    TEXT_WRAP = 1
    TEXT_MODES = {TEXT_NOWRAP, TEXT_WRAP}

    def __init__(self, lines:int=0, textMode:int=0, hasBorder:bool=False):
        """
        Initializes the header buffer and display configuration.

        Args:
            lines (int): Maximum number of text rows stored.
            textMode (int): Text handling mode (TEXT_NOWRAP or TEXT_WRAP).
            hasBorder (bool): Render border between header and text.
        """
        self.textMode = self.textMode = textMode if textMode in self.TEXT_MODES else self.TEXT_NOWRAP
        self.hasBorder = hasBorder

        # text
        self.rows = lines
        self.text = deque(maxlen=self.rows)

class Border:
    """
    Generates terminal border strings using predefined box-drawing
    styles or a custom character sequence.
    """
    class Charset:
        """
        Defines a character set used for drawing UI borders, boxes, and symbols.

        The charset string is expanded or truncated to a fixed length of 18
        characters and mapped to specific drawing primitives such as lines,
        corners, junctions, and arrow indicators.

        Attributes:
            CHARSET_LEN (int): Required length of the internal charset (18 chars).

            lineH (str): Horizontal line character.
            lineV (str): Vertical line character.

            cornerNW (str): Top-left corner.
            cornerNE (str): Top-right corner.
            cornerSW (str): Bottom-left corner.
            cornerSE (str): Bottom-right corner.

            junctionVE (str): Vertical-then-east junction.
            junctionVW (str): Vertical-then-west junction.
            junctionHS (str): Horizontal-then-south junction.
            junctionHN (str): Horizontal-then-north junction.
            junctionAll (str): Four-way junction.

            boxLower (str): Lower block character.
            boxUpper (str): Upper block character.
            boxFull (str): Full block character.

            arrowUp (str): Up arrow symbol.
            arrowDown (str): Down arrow symbol.
            arrowLeft (str): Left arrow symbol.
            arrowRight (str): Right arrow symbol.
        """
        CHARSET_LEN = 18
        def __init__(self, charset:str):
            """
            Initialize a Charset mapping used for drawing UI elements.

            The input string is expanded or truncated to exactly 18 characters,
            then each character is assigned to a specific graphical role used
            for rendering borders, junctions, blocks, and arrows.

            Args:
                charset (str): A string defining the visual character set.
                    If None or empty, a single space character is used.
            """
            if charset is None or len(charset) == 0:
                charset = " "
            charset = (charset * ((self.CHARSET_LEN // len(charset)) + 1))[:self.CHARSET_LEN]
            self.lineH = charset[0]
            self.lineV = charset[1]
            self.cornerNW = charset[2]
            self.cornerNE = charset[3]
            self.cornerSW = charset[4]
            self.cornerSE = charset[5]
            self.junctionVE = charset[6]
            self.junctionVW = charset[7]
            self.junctionHS = charset[8]
            self.junctionHN = charset[9]
            self.junctionAll = charset[10]
            self.boxLower = charset[11]
            self.boxUpper = charset[12]
            self.boxFull = charset[13]
            self.arrowUp = charset[14]
            self.arrowDown = charset[15]
            self.arrowLeft = charset[16]
            self.arrowRight = charset[17]

    NO_BORDER = 0
    CUSTOM = 1
    SINGLE_BOX = 2
    DOUBLE_BOX = 3
    HEAVY_BOX = 4
    ASCII = 5
    BORDER_STYLES = {NO_BORDER, CUSTOM, SINGLE_BOX, DOUBLE_BOX, HEAVY_BOX, ASCII}
    BORDER_CHARS = {NO_BORDER:  "",
                    CUSTOM:     "",
                    SINGLE_BOX: "─│┌┐└┘├┤┬┴┼▄▀█▲▼⯇⯈",
                    DOUBLE_BOX: "═║╔╗╚╝╠╣╦╩╬▄▀█▲▼⯇⯈",
                    HEAVY_BOX:  "━┃┏┓┗┛┣┫┳┻╋▄▀█▲▼⯇⯈",
                    ASCII:      "-|+++++++++###^v<>"
                    }

    def __init__(self, style: int = None, charset: str = None):
        """
        Border constructor.

        Args:
            style (int): Border style.
            charset (str): Custom border character(s). If this is not None, border.style is set to CUSTOM.
        """
        self.style = style if style in self.BORDER_STYLES else self.NO_BORDER
        if charset is not None:
            self.style = self.CUSTOM
        else:
            charset = self.BORDER_CHARS[self.style]
        self.charset = self.Charset(charset)

    def getTop(self, width:int)->str:
        """
        Returns the top border line for the specified width.

        Args:
            width (int): Total width of the border line.

        Returns:
            str: Rendered top border string.
        """
        return self.charset.cornerNW + self.charset.lineH * (width - 2) + self.charset.cornerNE

    def getMiddle(self, width:int):
        """
        Returns the middle separator border line for the specified width.

        Args:
            width (int): Total width of the border line.

        Returns:
            str: Rendered middle border string.
        """
        return self.charset.junctionVE + self.charset.lineH * (width - 2) + self.charset.junctionVW

    def getBottom(self, width:int):
        """
        Returns the bottom border line for the specified width.

        Args:
            width (int): Total width of the border line.

        Returns:
            str: Rendered bottom border string.
        """
        return self.charset.cornerSW + self.charset.lineH * (width - 2) + self.charset.cornerSE

class Tile:
    """
    A terminal UI region that renders a bordered rectangular tile
    with an optional header and scrollable/wrappable text buffer.
    """
    TEXT_NOWRAP = 0
    TEXT_WRAP = 1
    TEXT_MODES = {TEXT_NOWRAP, TEXT_WRAP}
    SIZE_FIXED = 0
    SIZE_SCROLLING = 1
    SIZE_MODES = {SIZE_FIXED, SIZE_SCROLLING}

    def __init__(self, fd:int, x:int, y:int, width:int, height:int, name:str, textMode:int, sizeMode:int, border:Border, header:Header):
        """
        Initializes a Tile UI component that represents a bordered
        terminal region with an optional header and scrollable text buffer.

        Args:
            fd (int): File descriptor used for direct terminal output.
            x (int): Column position of the tile (1-based terminal coords).
            y (int): Row position of the tile (1-based terminal coords).
            width (int): Total width of the tile including borders.
            height (int): Total height of the tile including borders.
            name (str): Identifier for the tile.
            textMode (int): Text rendering mode (wrap or no-wrap).
            border (Border): Border style/renderer instance.
            header (Header): Header configuration and buffer.
        """
        self.x = x #col
        self.y = y #row
        self.width = width 
        self.height = height 
        self.name = name 
        self.textMode = textMode if textMode in self.TEXT_MODES else self.TEXT_NOWRAP
        self.sizeMode = sizeMode if sizeMode in self.SIZE_MODES else self.SIZE_FIXED
        self.border = border
        self.header = header
        self.fd = fd

        # colors
        self.colors = {
            "BORDER_FG": None,
            "BORDER_BG": None,
            "HEADER_FG": None,
            "HEADER_BG": None,
            "TEXT_FG": None,
            "TEXT_BG": None,
            "BORDER_FG_F": None,
            "BORDER_BG_F": None,
            "HEADER_FG_F": None,
            "HEADER_BG_F": None,
            "TEXT_FG_F": None,
            "TEXT_BG_F": None
        }

        # text
        self.rows = height - self.header.rows
        self.cols = self.width
        self.tx = self.x
        self.ty = self.y + self.header.rows
        self.hx = self.x
        self.hy = self.y
        if self.border.style != Border.NO_BORDER:
            self.tx += 1
            self.ty += 1
            self.rows -= 2
            self.cols -= 2
            self.hx += 1
            self.hy += 1
        if self.header.hasBorder:
            self.ty += 1
            self.rows -= 1

        if self.sizeMode == self.SIZE_SCROLLING:
            self.cols -= 2

        if self.sizeMode == self.SIZE_FIXED:
            self.text = deque(maxlen=self.rows)
        else:
            self.text = []
        self.tIndex = 0

        self.focused = False
        self.drawBorder()

    def setColor(self, fg:tuple, bg:tuple):
        # fg
        if not fg is None:
            os.write(self.fd, f"\033[38;2;{fg[0]};{fg[1]};{fg[2]}m".encode())
        # bg
        if not bg is None:
            os.write(self.fd, f"\033[48;2;{bg[0]};{bg[1]};{bg[2]}m".encode())

    def resetColor(self):
        os.write(self.fd, f"\033[0m".encode())

    def drawBorder(self):
        """
        Draws:
            - Left and right vertical border lines
            - Top border line
            - Optional header separator (middle border)
            - Bottom border line
        """
        if self.focused:
            self.setColor(self.colors["BORDER_FG_F"], self.colors["BORDER_BG_F"])
        else:
            self.setColor(self.colors["BORDER_FG"], self.colors["BORDER_BG"])

        for row in range(self.y + 1, self.y + self.height):
            os.write(self.fd, f"\x1b[{row};{self.x}H{self.border.charset.lineV}".encode())
            os.write(self.fd, f"\x1b[{row};{self.x + self.width - 1}H{self.border.charset.lineV}".encode())

        os.write(self.fd, f"\x1b[{self.y};{self.x}H{self.border.getTop(self.width)}".encode())
        os.write(self.fd, f"\x1b[{self.y + self.header.rows + 1};{self.x}H{self.border.getMiddle(self.width)}".encode())
        os.write(self.fd, f"\x1b[{self.y + self.height - 1};{self.x}H{self.border.getBottom(self.width)}".encode())

        self.resetColor()

    def drawScrollbar(self):
        #top
        os.write(self.fd, f"\x1b[{self.y + self.header.rows + 1};{self.x + self.width - 3}H{self.border.charset.junctionHS + self.border.charset.lineH + self.border.charset.junctionVW}".encode())
        #middle
        for row in range(self.y + self.header.rows + 2, self.y + self.height - 1):
            os.write(self.fd, f"\x1b[{row};{self.x + self.width - 3}H{self.border.charset.lineV + ' ' + self.border.charset.lineV}".encode())
        #bottom
        os.write(self.fd, f"\x1b[{self.y + self.height - 1};{self.x + self.width - 3}H{self.border.charset.junctionHN + self.border.charset.lineH + self.border.charset.cornerSE}".encode())

        #bar
        bar_offset = (self.rows - 1) * self.tIndex / max(len(self.text) - self.rows, 1)

        if self.border.style == Border.ASCII:
            bar_offset = round(bar_offset)
        else:
            bar_offset = round(bar_offset * 2) / 2

            if bar_offset > (self.rows - 1):
                bar_offset = self.rows - 1

        bar1 = int(bar_offset)
        bar2 = int(bar_offset + 0.5)
        # self.update(f"bar1: {bar1} bar2: {bar2}, tIndex: {self.tIndex}, len: {len(self.text)}")
        if bar1 == bar2:
            os.write(self.fd, f"\x1b[{self.y + self.header.rows + 2 + bar1};{self.x + self.width - 2}H{self.border.charset.boxFull}".encode())
        else:
            os.write(self.fd, f"\x1b[{self.y + self.header.rows + 2 + bar1};{self.x + self.width - 2}H{self.border.charset.boxLower}".encode())
            os.write(self.fd, f"\x1b[{self.y + self.header.rows + 2 + bar2};{self.x + self.width - 2}H{self.border.charset.boxUpper}".encode())

    def update(self, text:str):
        """
        Appends new text to the tile's internal buffer and renders
        the visible text region in the terminal.
        """
        for line in text.split('\n'):
            if self.textMode == self.TEXT_NOWRAP:
                output = line[:self.cols]
                self.text.append(output + ' ' * (self.cols - len(output)))
                if len(self.text) > self.rows:
                    self.tIndex += 1
            elif self.textMode == self.TEXT_WRAP:
                for i in range(0, len(line), self.cols):
                    output = line[i:i+self.cols]
                    self.text.append(output + ' ' * (self.cols - len(output)))
                    if len(self.text) > self.rows:
                        self.tIndex += 1

        row = self.ty
        for line in list(self.text)[self.tIndex:]:
            os.write(self.fd, f"\x1b[{row};{self.tx}H{line}".encode())
            row += 1

    def updateHeader(self, text:str):
        """
        Appends new text to the tile's header buffer and renders
        the visible header region in the terminal.
        """
        for line in text.split('\n'):
            if self.textMode == self.TEXT_NOWRAP:
                output = line[:self.cols]
                self.header.text.append(output + ' ' * (self.cols - len(output)))
            elif self.textMode == self.TEXT_WRAP:
                for i in range(0, len(line), self.cols):
                    output = line[i:i+self.cols]
                    self.header.text.append(output + ' ' * (self.cols - len(output)))

        row = self.hy
        for line in self.header.text:
            os.write(self.fd, f"\x1b[{row};{self.hx}H{line}".encode())
            row += 1

class InputField:
    """
    A fixed-size terminal input widget supporting interactive text editing.
    """
    def __init__(self, fd:int, keyboard:Keyboard, x:int, y:int, width:int, height:int, name:str, visible:bool, prompt:str, border:Border):
        """
        Initializes a terminal input widget with a fixed-size grid layout.

        Configures geometry (position, width, height), optional border offsets,
        prompt rendering, and input capacity limits.

        Args:
            fd (int): Terminal file descriptor.
            keyboard (Keyboard): Keyboard reader.
            x (int): Column position.
            y (int): Row position.
            width (int): Widget width.
            height (int): Widget height.
            name (str): Identifier for the widget.
            visible (bool): Whether to render immediately.
            prompt (str): Prompt text displayed above input area.
            border (Border): Border configuration.
        """
        self.fd = fd
        self.keyboard = keyboard
        self.x = x #col
        self.y = y #row
        self.width = width 
        self.height = height 

        # text
        self.rows = self.height
        self.cols = self.width
        self.tx = self.x
        self.ty = self.y
        self.border = border
        if self.border.style != Border.NO_BORDER:
            self.tx += 1
            self.ty += 1
            self.rows -= 2
            self.cols -= 2

        self.prompt = []
        self.pIndex = 0
        self.px = self.tx
        self.py = self.ty
        self.setPrompt(prompt)
        self.inputMax = (self.rows - len(self.prompt)) * self.cols + (self.cols - (self.px - self.tx)) # max num of chars for input

        self.name = name 
        self.visible = visible
        if self.visible:
            self.show()

    def setPrompt(self, prompt: str):
        """
        Formats and stores the prompt into fixed-width terminal rows.

        Splits the prompt by newline and wraps each line to self.cols width,
        padding rows to full width. Truncates to fit within self.rows.

        Sets:
            self.prompt: list of fixed-width rows
            self.py: prompt end row (Y position)
            self.px: X position after last prompt character
        """
        self.prompt = []
        promptBuffer = 0

        for line in prompt.split('\n'):
            for i in range(0, len(line), self.cols):
                chunk = line[i:i + self.cols]
                self.prompt.append(chunk + ' ' * (self.cols - len(chunk)))
                promptBuffer = self.cols - len(chunk)

        self.prompt = self.prompt[:self.rows]
        self.py = self.ty + max(len(self.prompt) - 1, 0)
        self.px = self.tx + len(self.prompt[-1]) - promptBuffer

    def show(self):
        """
        Shows InputField
        """
        self.drawBorder()
        # render text
        row = self.ty
        for line in self.prompt:
            os.write(self.fd, f"\x1b[{row};{self.tx}H{line}".encode())
            row += 1

    def hide(self):
        """
        Hides InputField
        """
        for i, _ in enumerate(self.rows):
            os.write(self.fd, f"\x1b[{self.x};{self.y + i}H{' ' * self.width}".encode())

    def drawBorder(self):
        """
        Draws:
            - Left and right vertical border lines
            - Top border line
            - Bottom border line
        """
        for row in range(self.y + 1, self.y + self.height):
            os.write(self.fd, f"\x1b[{row};{self.x}H{self.border.charset.lineV}".encode())
            os.write(self.fd, f"\x1b[{row};{self.x + self.width - 1}H{self.border.charset.lineV}".encode())

        os.write(self.fd, f"\x1b[{self.y};{self.x}H{self.border.getTop(self.width)}".encode())
        os.write(self.fd, f"\x1b[{self.y + self.height - 1};{self.x}H{self.border.getBottom(self.width)}".encode())

    def updateInput(self, cursorX:int, cursorY:int, text:str):
        """
        Clears and overwrites input starting at given cursor position.

        Args:
            cursorX (int): Current cursor X position in terminal coordinates.
            cursorY (int): Current cursor Y position in terminal coordinates.
            text (str): Full input buffer to render.
        """
        offset = 0
        offset = 0

        if cursorY == self.py:
            # first row
            offset += cursorX - self.px
        else:
            # usable chars on first row
            offset += self.cols - (self.px - self.tx)

            # full wrapped rows
            offset += (cursorY - self.py - 1) * self.cols

            # current row offset
            offset += cursorX - self.tx

        # write
        cX, cY = cursorX, cursorY
        t = ''.join(text) + ' ' * (self.inputMax - len(text))
        for c in t[offset:]:
            os.write(self.fd, f"\033[{cY};{cX}H{c}".encode())
            cX += 1

            if cX >= self.tx + self.cols:
                cX = self.tx
                cY += 1

    def getInput(self)->str:
        """
        Runs an interactive terminal line editor and returns the final input string.

        Supports real-time keyboard navigation and editing within a fixed-width terminal
        input region starting at (px, py) and spanning a grid of size (rows x cols).

        Returns:
            str: The final edited input string after Enter is pressed.
        """
        self.pIndex = 0
        # move cursor
        os.write(self.fd, f"\033[{self.py};{self.px}H".encode())
        cursorX = self.px
        cursorY = self.py

        # handle keyboard input
        s = []
        k = None
        while k != Keyboard.KEY_ENTER:
            # show cursor
            os.write(self.fd, "\033[?25h".encode())
            k = self.keyboard.getKey()
            # hide cursor
            os.write(self.fd, "\033[?25l".encode())

            if k == Keyboard.KEY_LEFT:
                if cursorY == self.py:
                    # cursorX cannot be < px
                    if cursorX > self.px:
                        cursorX -= 1
                        self.pIndex -= 1
                        os.write(self.fd, f"\033[{cursorY};{cursorX}H".encode())
                else:
                    # cursorX cannot be < tx
                    if cursorX == self.tx:
                        # move cursor to previous line
                        cursorY -= 1
                        cursorX = self.tx + self.cols - 1
                        self.pIndex -= 1
                        os.write(self.fd, f"\033[{cursorY};{cursorX}H".encode())
                    else:
                        cursorX -= 1
                        self.pIndex -= 1
                        os.write(self.fd, f"\033[{cursorY};{cursorX}H".encode())

            elif k == Keyboard.KEY_RIGHT:
                if self.pIndex < len(s):
                    self.pIndex += 1

                    idx = self.pIndex

                    firstWidth = self.cols - (self.px - self.tx)

                    if idx < firstWidth:
                        cursorY = self.py
                        cursorX = self.px + idx
                    else:
                        idx -= firstWidth
                        cursorY = self.py + 1 + (idx // self.cols)
                        cursorX = self.tx + (idx % self.cols)
                    
                    # adjust if at end of buffer
                    if self.pIndex == self.inputMax:
                        cursorX = self.tx + self.cols
                        cursorY -= 1

                    os.write(self.fd, f"\033[{cursorY};{cursorX}H".encode())

            elif k == Keyboard.KEY_BACKSPACE:
                if self.pIndex > 0:
                    # move logical cursor backward
                    self.pIndex -= 1

                    # move visual cursor backward
                    if cursorY == self.py:
                        if cursorX > self.px:
                            cursorX -= 1
                    else:
                        if cursorX == self.tx:
                            cursorY -= 1

                            # previous row may be prompt row
                            if cursorY == self.py:
                                cursorX = self.px + (self.cols - (self.px - self.tx)) - 1
                            else:
                                cursorX = self.tx + self.cols - 1
                        else:
                            cursorX -= 1

                    # remove char from buffer
                    del s[self.pIndex]

                    # redraw shifted text
                    self.updateInput(cursorX, cursorY, s)

                    # restore cursor
                    os.write(self.fd, f"\033[{cursorY};{cursorX}H".encode())

            elif k == Keyboard.KEY_DELETE:
                # cannot delete past end of input
                if self.pIndex < len(s):
                    # remove char at cursor
                    del s[self.pIndex]

                    # redraw shifted text starting at current cursor
                    self.updateInput(cursorX, cursorY, s)

                    # restore cursor
                    os.write(self.fd, f"\033[{cursorY};{cursorX}H".encode())

            elif k == Keyboard.KEY_HOME:
                self.pIndex = 0
                cursorX = self.px
                cursorY = self.py

                # move cursor
                os.write(self.fd, f"\033[{cursorY};{cursorX}H".encode())

            elif k == Keyboard.KEY_END:
                self.pIndex = len(s)

                total = len(s)

                firstWidth = self.cols - (self.px - self.tx)

                if total < firstWidth:
                    cursorY = self.py
                    cursorX = self.px + total
                else:
                    total -= firstWidth

                    cursorY = self.py + 1 + (total // self.cols)
                    cursorX = self.tx + (total % self.cols)

                # adjust if at end of buffer
                if len(s) == self.inputMax:
                    cursorX = self.tx + self.cols
                    cursorY -= 1

                os.write(self.fd, f"\033[{cursorY};{cursorX}H".encode())

            elif k == Keyboard.KEY_ESCAPE:
                s = []
                cursorX = self.px
                cursorY = self.py
                self.pIndex = 0
                self.updateInput(self.px, self.py, "")
                os.write(self.fd, f"\033[{cursorY};{cursorX}H".encode())

            elif Keyboard.isPrintable(k) and len(s) < self.inputMax:
                # insert char into buffer
                s.insert(self.pIndex, k)
                self.pIndex += 1

                # write
                self.updateInput(cursorX, cursorY, s)

                # move cursor
                cursorX += 1
                if (cursorX > self.tx + self.cols - 1) and len(s) < self.inputMax:
                    cursorX = self.tx
                    cursorY += 1
                os.write(self.fd, f"\033[{cursorY};{cursorX}H".encode())

        # clear input
        self.updateInput(self.px, self.py, "")

        return "".join(s)

class TerminalTiler:
    """
    Manages a collection of Tile objects to build a structured
    terminal UI layout.

    Provides functionality for creating, positioning, and updating
    multiple independent terminal regions (tiles), each with its
    own border, header, and text buffer.
    """
    def __init__(self):
        """
        Initializes the TerminalTiler UI system.

        On Windows, switches the console code page to UTF-8 to support
        Unicode box-drawing characters. Then queries the terminal size,
        initializes the tile registry, and installs an FDInterceptor on
        standard output for capturing or redirecting terminal output.
        """
        if os.name == "nt":
            os.system("chcp 65001 > nul") #switch to unicode charset
        self.cols, self.rows = os.get_terminal_size()
        self.tiles = {}
        self.names = []
        self.activeTileIndex = -1
        self.inputFields = {}
        self.stdout_FDI = FDInterceptor(1)
        self.keyboard = Keyboard()
        self.keyboard.mapKey(Keyboard.KEY_UP, self.handleInput)
        self.keyboard.mapKey(Keyboard.KEY_DOWN, self.handleInput)
        self.keyboard.mapKey(Keyboard.KEY_TAB, self.handleInput)
        self.keyboard.start()

    def addTile(self, x:int, y:int, width:int, height:int, name:str, textMode:int=None, sizeMode:int=None, borderStyle:int=None, borderChar:str=None, headerLines:int=0, headerMode:int=None, headerBorder:bool=False):
        """
        Creates and registers a new Tile in the terminal layout.

        Performs boundary validation against the terminal size to ensure
        the tile fits within the visible viewport. Then constructs a Tile
        instance with the specified border and header configuration and
        stores it in the tile registry under the provided name.

        Args:
            x (int): Tile origin column (1-based).
            y (int): Tile origin row (1-based).
            width (int): Tile width in characters.
            height (int): Tile height in rows.
            name (str): Unique identifier for the tile.
            textMode (int, optional): TEXT_WRAP or TEXT_NOWRAP.
            sizeMode (int, optional): SIZE_FIXED or SIZE_SCROLLING.
            borderStyle (int, optional): Border style constant.
            borderChar (str, optional): Custom border character.
            headerLines (int): Number of header rows.
            headerMode (int, optional): Header text mode.
            headerBorder (bool): Whether header has its own border.
        """
        #check dimensions
        if x <= 0 or x >= self.cols or y <= 0 or y >= self.rows:
            raise ValueError("Tile origin is not contained by terminal")
        elif x + width >= self.cols:
            raise ValueError("Tile exceeds terminal boundary (X-axis)")
        elif y + height >= self.rows:
            raise ValueError("Tile exceeds terminal boundary (Y-axis)")

        if len(self.tiles) > 0:
            self.tiles[self.names[self.activeTileIndex]].focused = False
        self.tiles[name] = Tile(self.stdout_FDI.real_fd, x, y, width, height, name, textMode, sizeMode, Border(borderStyle, borderChar), Header(headerLines, headerMode, headerBorder))
        self.names.append(name)
        self.activeTileIndex += 1

    def addInputField(self, x:int, y:int, width:int, height:int, name:str, visible:bool, prompt:str="", borderStyle:int=None, borderChar:str=None):
        """
        Creates and registers a new InputField in the terminal layout.

        Performs boundary validation against the terminal size to ensure
        the tile fits within the visible viewport. Then constructs a Tile
        instance with the specified border and header configuration and
        stores it in the tile registry under the provided name.

        Args:
            x (int): Tile origin column (1-based).
            y (int): Tile origin row (1-based).
            width (int): Tile width in characters.
            height (int): Tile height in rows.
            name (str): Unique identifier for the tile.
            visible (bool): Show prompt?
            prompt (str): Input prompt.
            borderStyle (int, optional): Border style constant.
            borderChar (str, optional): Custom border character.
        """
        #check dimensions
        if x <= 0 or x >= self.cols or y <= 0 or y >= self.rows:
            raise ValueError("Tile origin is not contained by terminal")
        elif x + width >= self.cols:
            raise ValueError("Tile exceeds terminal boundary (X-axis)")
        elif y + height >= self.rows:
            raise ValueError("Tile exceeds terminal boundary (Y-axis)")

        self.inputFields[name] = InputField(self.stdout_FDI.real_fd, self.keyboard, x, y, width, height, name, visible, prompt, Border(borderStyle, borderChar))

    def handleInput(self, key:str):
        #TODO hide/move cursor
        if key == Keyboard.KEY_TAB:
            if len(self.tiles) > 0 and self.activeTileIndex >= 0:
                self.tiles[self.names[self.activeTileIndex]].focused = False
                self.tiles[self.names[self.activeTileIndex]].drawBorder()
            if len(self.tiles) > 0:
                self.activeTileIndex += 1
                self.activeTileIndex %= len(self.tiles)
                self.tiles[self.names[self.activeTileIndex]].focused = True
                self.tiles[self.names[self.activeTileIndex]].drawBorder()

        elif key == Keyboard.KEY_UP:
            pass
        elif key == Keyboard.KEY_DOWN:
            pass

    def clearScreen(self):
        """
        Clears terminal screen.
        """
        os.write(self.stdout_FDI.real_fd, "\x1b[2J".encode())

    def hide_cursor(self):
        """
        Hides cursor.
        """
        os.write(self.stdout_FDI.real_fd, "\033[?25l".encode())

    def show_cursor(self):
        """
        Shows cursor.
        """
        os.write(self.stdout_FDI.real_fd, "\033[?25h".encode())

    def close(self):
        """
        Finalizes the terminal UI session.

        Moves the cursor to the bottom-most rendered tile region to avoid
        leaving the cursor inside a UI block, restores the terminal cursor
        visibility, and shuts down the stdout FDInterceptor cleanly.
        """
        maxY = max(tile.y + tile.height for tile in [*self.tiles.values(), *self.inputFields.values()])
        os.write(self.stdout_FDI.real_fd, f"\x1b[{maxY};{1}H".encode())

        self.show_cursor()
        self.stdout_FDI.close()