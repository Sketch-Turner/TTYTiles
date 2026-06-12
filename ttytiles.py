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
    KEY_PAGE_UP = "PAGE_UP"
    KEY_PAGE_DOWN = "PAGE_DOWN"
    KEY_CTRL_C = "CTRL_C"
    PRINTABLE = set([chr(c) for c in range(32, 127)])

    def __init__(self):
        """
        Initialize the keyboard input handler.
        """
        self.subscribers = set()
        self.exit = None
        self.thread = None

    def start(self, exit_event):
        """
        Starts the background keyboard reader thread.
        """
        self.exit = exit_event
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def subscribe(self, func):
        """
        Register a callback function for key presses.
        Args:
            func (callable): Function to execute when a key is pressed.
        """
        self.subscribers.add(func)

    def _read(self):
        """
        Internal keyboard polling loop.

        Continuously reads raw key input and dispatches it to all mapped
        handlers.
        """
        while True:
            if self.exit.is_set():
                break
            k = self._readKey()

            for func in self.subscribers:
                if not func is None:
                    func(k)

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
                    "I": Keyboard.KEY_PAGE_UP,
                    "Q": Keyboard.KEY_PAGE_DOWN,
                }.get(code, code)

            if ch == "\r":
                return Keyboard.KEY_ENTER

            if ch == "\t":
                return Keyboard.KEY_TAB

            if ch == "\x08":
                return Keyboard.KEY_BACKSPACE

            if ch == "\x1b":
                return Keyboard.KEY_ESCAPE

            if ch == "\x03":
                return Keyboard.KEY_CTRL_C

            return ch

        else:
            fd = sys.stdin.fileno()

            old = termios.tcgetattr(fd)

            try:
                tty.setraw(fd)

                ch = os.read(fd, 1)

                # Ctrl+C
                if ch == b"\x03":
                    return Keyboard.KEY_CTRL_C

                # Escape / escape sequences
                if ch == b"\x1b":
                    seq = b"\x1b"

                    while True:
                        r, _, _ = select.select([fd], [], [], 0.03)

                        if not r:
                            break

                        seq += os.read(fd, 1)

                    return {
                        b"\x1b[A": Keyboard.KEY_UP,
                        b"\x1b[B": Keyboard.KEY_DOWN,
                        b"\x1b[C": Keyboard.KEY_RIGHT,
                        b"\x1b[D": Keyboard.KEY_LEFT,

                        b"\x1b[H": Keyboard.KEY_HOME,
                        b"\x1b[F": Keyboard.KEY_END,

                        b"\x1bOH": Keyboard.KEY_HOME,  # xterm variant
                        b"\x1bOF": Keyboard.KEY_END,

                        b"\x1b[3~": Keyboard.KEY_DELETE,

                        b"\x1b[5~": Keyboard.KEY_PAGE_UP,
                        b"\x1b[6~": Keyboard.KEY_PAGE_DOWN,
                    }.get(seq, Keyboard.KEY_ESCAPE)

                if ch in (b"\r", b"\n"):
                    return Keyboard.KEY_ENTER

                if ch == b"\t":
                    return Keyboard.KEY_TAB

                if ch in (b"\x7f", b"\x08"):
                    return Keyboard.KEY_BACKSPACE

                return ch.decode(errors="ignore")

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
    def __init__(self, fd:int, exit_event:threading.Event):
        """
        Redirects the specified file descriptor into an internal pipe,
        starts a relay thread, and captures all future output written
        to the descriptor.

        Args:
            fd (int): File descriptor to intercept (Currently only supports STDIN).
            exit_event (threading.Event): Exit flag.
        """
        self.default_target = None
        self.fd = fd
        self.exit = exit_event

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
            while True:
                if self.exit.is_set():
                    # kill thread
                    break
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
        Stops interception, restores the original file descriptor and
        closes internal pipe resources.
        """
        self.exit.set()

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

class DisplayTile:
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

    def __init__(self, writer_func, x:int, y:int, width:int, height:int, textMode:int, sizeMode:int, border:Border, header:Header):
        """
        Initializes a DisplayTile UI component that represents a bordered
        terminal region with an optional header and scrollable text buffer.

        Args:
            writer_func: Used to write to terminal.
            x (int): Column position of the tile (1-based terminal coords).
            y (int): Row position of the tile (1-based terminal coords).
            width (int): Total width of the tile including borders.
            height (int): Total height of the tile including borders.
            textMode (int): Text rendering mode (wrap or no-wrap).
            border (Border): Border style/renderer instance.
            header (Header): Header configuration and buffer.
        """
        self.x = x #col
        self.y = y #row
        self.width = width 
        self.height = height 
        self.textMode = textMode if textMode in self.TEXT_MODES else self.TEXT_NOWRAP
        self.sizeMode = sizeMode if sizeMode in self.SIZE_MODES else self.SIZE_FIXED
        self.border = border
        self.header = header
        self.write = writer_func

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
        self.canFocus = True
        self.drawBorder()

    def drawBorder(self):
        """
        Draws:
            - Left and right vertical border lines
            - Top border line
            - Optional header separator (middle border)
            - Bottom border line
        """
        if self.focused:
            color_fg = self.colors["BORDER_FG_F"]
            color_bg = self.colors["BORDER_BG_F"]
        else:
            color_fg = self.colors["BORDER_FG"]
            color_bg = self.colors["BORDER_BG"]

        for row in range(self.y + 1, self.y + self.height):
            self.write(f"\x1b[{row};{self.x}H{self.border.charset.lineV}".encode(), color_fg, color_bg)
            self.write(f"\x1b[{row};{self.x + self.width - 1}H{self.border.charset.lineV}".encode(), color_fg, color_bg)

        self.write(f"\x1b[{self.y};{self.x}H{self.border.getTop(self.width)}".encode(), color_fg, color_bg)
        if self.header.hasBorder:
            self.write(f"\x1b[{self.y + self.header.rows + 1};{self.x}H{self.border.getMiddle(self.width)}".encode(), color_fg, color_bg)
        self.write(f"\x1b[{self.y + self.height - 1};{self.x}H{self.border.getBottom(self.width)}".encode(), color_fg, color_bg)

        if self.sizeMode == self.SIZE_SCROLLING:
            self.drawScrollbarBorder()
            self.drawScrollbar()

    def drawScrollbarBorder(self):
        """
        Draws the right-side scrollbar border.
        """
        if self.focused:
            color_fg = self.colors["BORDER_FG_F"]
            color_bg = self.colors["BORDER_BG_F"]
        else:
            color_fg = self.colors["BORDER_FG"]
            color_bg = self.colors["BORDER_BG"]

        #top
        header_height = self.header.rows
        cornerTop = self.border.charset.cornerNE
        if self.header.hasBorder:
            header_height += 1
            cornerTop = self.border.charset.junctionVW
        self.write(f"\x1b[{self.y + header_height};{self.x + self.width - 3}H{self.border.charset.junctionHS + self.border.charset.lineH + cornerTop}".encode(), color_fg, color_bg)

        #middle
        for row in range(self.y + header_height + 1, self.y + self.height - 1):
            self.write(f"\x1b[{row};{self.x + self.width - 3}H{self.border.charset.lineV + ' ' + self.border.charset.lineV}".encode(), color_fg, color_bg)

        #bottom
        cornerBottom = self.border.charset.cornerSW
        if self.border.style != Border.NO_BORDER:
            cornerBottom = self.border.charset.junctionHN
        self.write(f"\x1b[{self.y + self.height - 1};{self.x + self.width - 3}H{cornerBottom + self.border.charset.lineH + self.border.charset.cornerSE}".encode(), color_fg, color_bg)

    def drawScrollbar(self):
        """
        Renders the scrollbar thumb inside the scrollbar track.
        """
        if self.focused:
            color_fg = self.colors["BORDER_FG_F"]
            color_bg = self.colors["BORDER_BG_F"]
        else:
            color_fg = self.colors["BORDER_FG"]
            color_bg = self.colors["BORDER_BG"]

        bar_top = self.y + self.header.rows
        if self.border.style != Border.NO_BORDER:
            bar_top += 1
        if self.header.hasBorder:
            bar_top += 1
        # clear
        for row in range(bar_top, self.y + self.height - 1):
            self.write(f"\x1b[{row};{self.x + self.width - 2}H ".encode(), color_fg, color_bg)

        # calc bar position
        max_scroll = max(len(self.text) - self.rows, 1)
        bar_offset = self.tIndex * (self.rows - 1) / max_scroll

        if self.border.style == Border.ASCII:
            bar_offset = round(bar_offset)
        else:
            bar_offset = round(bar_offset * 2) / 2

        if bar_offset > (self.rows - 1):
            bar_offset = self.rows - 1

        bar1 = int(bar_offset)
        bar2 = int(bar_offset + 0.5)

        # draw
        if bar1 == bar2:
            self.write(f"\x1b[{bar_top + bar1};{self.x + self.width - 2}H{self.border.charset.boxFull}".encode(), color_fg, color_bg)
        else:
            self.write(f"\x1b[{bar_top + bar1};{self.x + self.width - 2}H{self.border.charset.boxLower}".encode(), color_fg, color_bg)
            self.write(f"\x1b[{bar_top + bar2};{self.x + self.width - 2}H{self.border.charset.boxUpper}".encode(), color_fg, color_bg)

    def drawText(self):
        """
        Renders the visible portion of the text buffer to the terminal.
        """
        if self.focused:
            color_fg = self.colors["TEXT_FG_F"]
            color_bg = self.colors["TEXT_BG_F"]
        else:
            color_fg = self.colors["TEXT_FG"]
            color_bg = self.colors["TEXT_BG"]
        row = self.ty
        start = max(0, min(self.tIndex, len(self.text) - self.rows))
        for line in list(self.text)[start:start + self.rows]:
            self.write(f"\x1b[{row};{self.tx}H{line}".encode(), color_fg, color_bg)
            row += 1

    def update(self, text:str):
        """
        Appends new text to the tile's internal buffer and renders
        the visible text region in the terminal.

        Args:
            text (str): Text to add to text buffer.
        """
        for line in text.split('\n'):
            if self.textMode == self.TEXT_NOWRAP:
                output = line[:self.cols]
                self.text.append(output + ' ' * (self.cols - len(output)))
                self.tIndex = len(self.text) - 1
            elif self.textMode == self.TEXT_WRAP:
                for i in range(0, len(line), self.cols):
                    output = line[i:i+self.cols]
                    self.text.append(output + ' ' * (self.cols - len(output)))
                    self.tIndex += len(self.text) - 1

        # write text
        self.drawText()

        # update scrollbar position
        if self.sizeMode == self.SIZE_SCROLLING:
            self.drawScrollbar()

    def updateHeader(self, text:str):
        """
        Appends new text to the tile's header buffer and renders
        the visible header region in the terminal.

        Args:
            text (str): Text to add to text buffer.
        """
        for line in text.split('\n'):
            if self.textMode == self.TEXT_NOWRAP:
                output = line[:self.cols]
                self.header.text.append(output + ' ' * (self.cols - len(output)))
            elif self.textMode == self.TEXT_WRAP:
                for i in range(0, len(line), self.cols):
                    output = line[i:i+self.cols]
                    self.header.text.append(output + ' ' * (self.cols - len(output)))
        self.drawHeader()

    def drawHeader(self):
        """
        Renders header to terminal.
        """
        if self.focused:
            color_fg = self.colors["HEADER_FG_F"]
            color_bg = self.colors["HEADER_BG_F"]
        else:
            color_fg = self.colors["HEADER_FG"]
            color_bg = self.colors["HEADER_BG"]
        row = self.hy
        for line in self.header.text:
            self.write(f"\x1b[{row};{self.hx}H{line}".encode(), color_fg, color_bg)
            row += 1

    def handleInput(self, key:str):
        """
        Handles keyboard input to DisplayTile.

        Args:
            key (str): Key pressed.
        """
        if self.sizeMode == self.SIZE_SCROLLING:
            if key == Keyboard.KEY_UP:
                top = max(0, min(self.tIndex, len(self.text) - self.rows))
                if top > 0:
                    self.tIndex = top - 1
                    # text
                    self.drawText()

                    # scrollbar
                    self.drawScrollbar()

            elif key == Keyboard.KEY_DOWN:
                bottom = max(0, min(self.tIndex, len(self.text) - self.rows))
                if bottom < len(self.text) - self.rows:
                    self.tIndex = bottom + 1
                    # text
                    self.drawText()

                    # scrollbar
                    self.drawScrollbar()
            
            elif key == Keyboard.KEY_PAGE_UP:
                top = max(0, min(self.tIndex, len(self.text) - self.rows))
                if top > 0:
                    self.tIndex = 0
                    # text
                    self.drawText()

                    # scrollbar
                    self.drawScrollbar()

            elif key == Keyboard.KEY_PAGE_DOWN:
                bottom = max(0, min(self.tIndex, len(self.text) - self.rows))
                if bottom < len(self.text) - self.rows:
                    self.tIndex = len(self.text) - 1
                    # text
                    self.drawText()

                    # scrollbar
                    self.drawScrollbar()

    def show(self):
        """
        Renders DisplayTile
        """
        # hide cursor
        self.write("\033[?25l".encode())
        self.drawBorder()
        self.drawHeader()
        self.drawText()

    def hide(self):
        """
        Hides DisplayTile
        """
        # hide cursor
        self.write("\033[?25l".encode())
        for i in range(self.height):
            self.write(f"\x1b[{self.y + i};{self.x}H{' ' * self.width}".encode())

class InputTile:
    """
    A fixed-size terminal input widget supporting interactive text editing.
    """
    def __init__(self, write_func, exit_event:threading.Event, x:int, y:int, width:int, height:int, visible:bool, prompt:str, border:Border):
        """
        Initializes a terminal input widget with a fixed-size grid layout.

        Configures geometry (position, width, height), optional border offsets,
        prompt rendering, and input capacity limits.

        Args:
            writer_func: Used to write to terminal.
            exit_event (threading.Event): Exit flag.
            x (int): Column position.
            y (int): Row position.
            width (int): Tile width.
            height (int): Tile height.
            visible (bool): Whether to render immediately.
            prompt (str): Prompt text displayed above input area.
            border (Border): Border configuration.
        """
        self.exit = exit_event
        self.write = write_func
        self.x = x #col
        self.y = y #row
        self.width = width 
        self.height = height 

        # colors
        self.colors = {
            "BORDER_FG": None,
            "BORDER_BG": None,
            "INPUT_FG": None,
            "INPUT_BG": None,
            "TEXT_FG": None,
            "TEXT_BG": None,
            "BORDER_FG_F": None,
            "BORDER_BG_F": None,
            "INPUT_FG_F": None,
            "INPUT_BG_F": None,
            "TEXT_FG_F": None,
            "TEXT_BG_F": None
        }

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
        self.cursorX = self.px
        self.cursorY = self.py
        self.bufferMax = (self.rows - len(self.prompt)) * self.cols + (self.cols - (self.px - self.tx)) # max num of chars for input

        self.buffer = []
        self.input = queue.Queue()
        self.visible = visible
        self.focused = False
        self.canFocus = True
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
        Renders InputTile
        """
        # hide cursor
        self.write("\033[?25l".encode())
        self.drawBorder()
        self.drawText()
        cX, cY = self.cursorX, self.cursorY
        self.cursorX = self.px
        self.cursorY = self.py
        self.drawInput()
        # move cursor
        self.cursorX = cX
        self.cursorY = cY
        self.write(f"\033[{self.cursorY};{self.cursorX}H".encode())
        # show cursor
        self.write("\033[?25h".encode())

    def hide(self):
        """
        Hides InputTile
        """
        for i in range(self.height):
            self.write(f"\x1b[{self.y + i};{self.x}H{' ' * self.width}".encode())

    def drawText(self):
        """
        Renders prompt to terminal.
        """
        # render text
        if self.focused:
            color_fg = self.colors["TEXT_FG_F"]
            color_bg = self.colors["TEXT_BG_F"]
        else:
            color_fg = self.colors["TEXT_FG"]
            color_bg = self.colors["TEXT_BG"]
        row = self.ty
        for line in self.prompt:
            self.write(f"\x1b[{row};{self.tx}H{line}".encode(), color_fg, color_bg)
            row += 1

    def drawBorder(self):
        """
        Draws:
            - Left and right vertical border lines
            - Top border line
            - Bottom border line
        """
        if self.focused:
            color_fg = self.colors["BORDER_FG_F"]
            color_bg = self.colors["BORDER_BG_F"]
        else:
            color_fg = self.colors["BORDER_FG"]
            color_bg = self.colors["BORDER_BG"]

        for row in range(self.y + 1, self.y + self.height):
            self.write(f"\x1b[{row};{self.x}H{self.border.charset.lineV}".encode(), color_fg, color_bg)
            self.write(f"\x1b[{row};{self.x + self.width - 1}H{self.border.charset.lineV}".encode(), color_fg, color_bg)

        self.write(f"\x1b[{self.y};{self.x}H{self.border.getTop(self.width)}".encode(), color_fg, color_bg)
        self.write(f"\x1b[{self.y + self.height - 1};{self.x}H{self.border.getBottom(self.width)}".encode(), color_fg, color_bg)

    def drawInput(self):
        """
        Renders input field.
        """
        # normalize cursor
        if self.cursorX >= self.tx + self.cols:
            self.cursorX = self.tx
            self.cursorY += 1

        offset = 0
        if self.cursorY == self.py:
            # first row
            offset += self.cursorX - self.px
        else:
            # usable chars on first row
            offset += self.cols - (self.px - self.tx)

            # full wrapped rows
            offset += (self.cursorY - self.py - 1) * self.cols

            # current row offset
            offset += self.cursorX - self.tx

        # write
        if self.focused:
            color_fg = self.colors["INPUT_FG_F"]
            color_bg = self.colors["INPUT_BG_F"]
        else:
            color_fg = self.colors["INPUT_FG"]
            color_bg = self.colors["INPUT_BG"]

        cX, cY = self.cursorX, self.cursorY

        t = ''.join(self.buffer) + ' ' * (self.bufferMax - len(self.buffer))
        for c in t[offset:]:
            self.write(f"\033[{cY};{cX}H{c}".encode(), color_fg, color_bg)
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
        while not self.exit.is_set():
            try:
                return self.input.get(timeout=0.1)
            except queue.Empty:
                pass
        raise TerminalTiler.SIGINT()

    def handleInput(self, key:str):
        """
        Handles keyboard input.
        """
        # hide cursor
        self.write("\033[?25l".encode())

        if key == Keyboard.KEY_LEFT:
            if self.cursorY == self.py:
                # self.cursorX cannot be < px
                if self.cursorX > self.px:
                    self.cursorX -= 1
                    self.pIndex -= 1
                    self.write(f"\033[{self.cursorY};{self.cursorX}H".encode())
            else:
                # self.cursorX cannot be < tx
                if self.cursorX == self.tx:
                    # move cursor to previous line
                    self.cursorY -= 1
                    self.cursorX = self.tx + self.cols - 1
                    self.pIndex -= 1
                    self.write(f"\033[{self.cursorY};{self.cursorX}H".encode())
                else:
                    self.cursorX -= 1
                    self.pIndex -= 1
                    self.write(f"\033[{self.cursorY};{self.cursorX}H".encode())

        elif key == Keyboard.KEY_RIGHT:
            if self.pIndex < len(self.buffer):
                self.pIndex += 1

                idx = self.pIndex

                firstWidth = self.cols - (self.px - self.tx)

                if idx < firstWidth:
                    self.cursorY = self.py
                    self.cursorX = self.px + idx
                else:
                    idx -= firstWidth
                    self.cursorY = self.py + 1 + (idx // self.cols)
                    self.cursorX = self.tx + (idx % self.cols)
                
                # adjust if at end of buffer
                if self.pIndex == self.bufferMax:
                    self.cursorX = self.tx + self.cols
                    self.cursorY -= 1

                self.write(f"\033[{self.cursorY};{self.cursorX}H".encode())

        elif key == Keyboard.KEY_BACKSPACE:
            if self.pIndex > 0:
                # move logical cursor backward
                self.pIndex -= 1

                # move visual cursor backward
                if self.cursorY == self.py:
                    if self.cursorX > self.px:
                        self.cursorX -= 1
                else:
                    if self.cursorX == self.tx:
                        self.cursorY -= 1

                        # previous row may be prompt row
                        if self.cursorY == self.py:
                            self.cursorX = self.px + (self.cols - (self.px - self.tx)) - 1
                        else:
                            self.cursorX = self.tx + self.cols - 1
                    else:
                        self.cursorX -= 1

                # remove char from buffer
                del self.buffer[self.pIndex]

                # redraw shifted text
                self.drawInput()

                # restore cursor
                self.write(f"\033[{self.cursorY};{self.cursorX}H".encode())

        elif key == Keyboard.KEY_DELETE:
            # cannot delete past end of input
            if self.pIndex < len(self.buffer):
                # remove char at cursor
                del self.buffer[self.pIndex]

                # redraw shifted text starting at current cursor
                self.drawInput()

                # restore cursor
                self.write(f"\033[{self.cursorY};{self.cursorX}H".encode())

        elif key == Keyboard.KEY_HOME:
            self.pIndex = 0
            self.cursorX = self.px
            self.cursorY = self.py

            # move cursor
            self.write(f"\033[{self.cursorY};{self.cursorX}H".encode())

        elif key == Keyboard.KEY_END:
            self.pIndex = len(self.buffer)

            total = len(self.buffer)

            firstWidth = self.cols - (self.px - self.tx)

            if total < firstWidth:
                self.cursorY = self.py
                self.cursorX = self.px + total
            else:
                total -= firstWidth

                self.cursorY = self.py + 1 + (total // self.cols)
                self.cursorX = self.tx + (total % self.cols)

            # adjust if at end of buffer
            if len(self.buffer) == self.bufferMax:
                self.cursorX = self.tx + self.cols
                self.cursorY -= 1

            self.write(f"\033[{self.cursorY};{self.cursorX}H".encode())

        elif key == Keyboard.KEY_ESCAPE:
            self.buffer = []
            self.cursorX = self.px
            self.cursorY = self.py
            self.pIndex = 0
            self.drawInput()
            self.write(f"\033[{self.cursorY};{self.cursorX}H".encode())

        elif key == Keyboard.KEY_ENTER:
            self.input.put("".join(self.buffer))
            self.buffer = []
            self.pIndex = 0
            self.cursorX = self.px
            self.cursorY = self.py
            # clear input
            self.drawInput()
            self.cursorX = self.px
            self.cursorY = self.py
            self.write(f"\033[{self.cursorY};{self.cursorX}H".encode())

        elif Keyboard.isPrintable(key) and len(self.buffer) < self.bufferMax:
            # insert char into buffer
            self.buffer.insert(self.pIndex, key)
            self.pIndex += 1

            # write
            self.drawInput()

            # move cursor
            self.cursorX += 1
            if (self.cursorX > self.tx + self.cols - 1) and len(self.buffer) < self.bufferMax:
                self.cursorX = self.tx
                self.cursorY += 1
            self.write(f"\033[{self.cursorY};{self.cursorX}H".encode())

        # show cursor
        self.write("\033[?25h".encode())

class TerminalTiler:
    """
    Manages a collection of Tiles to build a structured
    terminal UI layout.

    Provides functionality for creating, positioning, and updating
    multiple independent terminal regions, each with its
    own border, header, and text buffer.
    """

    class SIGINT(Exception):
        """
        Thrown when exit threading event is set.
        """
        pass

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
        self.lock = threading.Lock()
        self.exit = threading.Event()
        self.cols, self.rows = os.get_terminal_size()
        self.focusedIndex = -1 # index of active element
        self.tiles = [] # holds all tile elements
        self.stdout_FDI = FDInterceptor(1, self.exit)
        self.keyboard = Keyboard()
        self.keyboard.subscribe(self.handleInput)
        self.keyboard.start(self.exit)
        self.hideCursor()
        self.clearScreen()

    def isAlive(self)->bool:
        """
        Checks whether the TerminalTiler is still running.

        Returns:
            bool: True if the shutdown event has not been set, otherwise False.
        """
        return not self.exit.is_set()

    def addDisplayTile(self, x:int, y:int, width:int, height:int, textMode:int=None, sizeMode:int=None, borderStyle:int=None, borderChar:str=None, headerLines:int=0, headerMode:int=None, headerBorder:bool=False)->DisplayTile:
        """
        Creates and registers a new DisplayTile in the terminal layout.

        Performs boundary validation against the terminal size to ensure
        the tile fits within the visible viewport. Then constructs a DisplayTile
        instance with the specified border and header configuration and
        stores it in the tile registry under the provided name.

        Args:
            x (int): DisplayTile origin column (1-based).
            y (int): DisplayTile origin row (1-based).
            width (int): DisplayTile width in characters.
            height (int): DisplayTile height in rows.
            textMode (int, optional): TEXT_WRAP or TEXT_NOWRAP.
            sizeMode (int, optional): SIZE_FIXED or SIZE_SCROLLING.
            borderStyle (int, optional): Border style constant.
            borderChar (str, optional): Custom border character.
            headerLines (int): Number of header rows.
            headerMode (int, optional): Header text mode.
            headerBorder (bool): Whether header has its own border.

        Returns:
            DisplayTile: DisplayTile object.
        """
        #check dimensions
        if x <= 0 or x >= self.cols or y <= 0 or y >= self.rows:
            raise ValueError("DisplayTile origin is not contained by terminal")
        elif x + width >= self.cols:
            raise ValueError("DisplayTile exceeds terminal boundary (X-axis)")
        elif y + height >= self.rows:
            raise ValueError("DisplayTile exceeds terminal boundary (Y-axis)")

        tile = DisplayTile(self.write, x, y, width, height, textMode, sizeMode, Border(borderStyle, borderChar), Header(headerLines, headerMode, headerBorder))
        self.tiles.append(tile)
        return tile

    def addInputTile(self, x:int, y:int, width:int, height:int, visible:bool, prompt:str="", borderStyle:int=None, borderChar:str=None)->InputTile:
        """
        Creates and registers a new InputTile in the terminal layout.

        Performs boundary validation against the terminal size to ensure
        the InputTile fits within the visible viewport. Then constructs an InputTile
        instance with the specified border and header configuration.

        Args:
            x (int): InputTile origin column (1-based).
            y (int): InputTile origin row (1-based).
            width (int): InputTile width in characters.
            height (int): InputTile height in rows.
            visible (bool): Show prompt?
            prompt (str): Input prompt.
            borderStyle (int, optional): Border style constant.
            borderChar (str, optional): Custom border character.

        Returns:
            InputTile: InputTile object.
        """
        #check dimensions
        if x <= 0 or x >= self.cols or y <= 0 or y >= self.rows:
            raise ValueError("InputTile origin is not contained by terminal")
        elif x + width >= self.cols:
            raise ValueError("InputTile exceeds terminal boundary (X-axis)")
        elif y + height >= self.rows:
            raise ValueError("InputTile exceeds terminal boundary (Y-axis)")

        field = InputTile(self.write, self.exit, x, y, width, height, visible, prompt, Border(borderStyle, borderChar))
        self.tiles.append(field)
        return field

    def handleInput(self, key:str):
        """
        Handles keyboard input for tile navigation and scrolling.
        """
        if key == Keyboard.KEY_TAB:
            # clear old focus
            if 0 <= self.focusedIndex and self.focusedIndex < len(self.tiles):
                self.tiles[self.focusedIndex].focused = False
                self.tiles[self.focusedIndex].show()

            # move forward
            self.focusedIndex += 1

            # find next focusable
            while (self.focusedIndex < len(self.tiles) and not self.tiles[self.focusedIndex].canFocus):
                self.focusedIndex += 1

            # apply or reset
            if self.focusedIndex < len(self.tiles):
                self.tiles[self.focusedIndex].focused = True
                self.tiles[self.focusedIndex].show()
            else:
                self.focusedIndex = -1
                self.hideCursor()

        elif key == Keyboard.KEY_CTRL_C:
            self.close()

        else:
            # send to element
            if self.focusedIndex >= 0:
                self.tiles[self.focusedIndex].handleInput(key)

    def clearScreen(self):
        """
        Clears terminal screen.
        """
        self.write("\x1b[2J".encode())

    def hideCursor(self):
        """
        Hides cursor.
        """
        self.write("\033[?25l".encode())

    def showCursor(self):
        """
        Shows cursor.
        """
        self.write("\033[?25h".encode())

    def write(self, text:bytes, fg_color:tuple[int, int, int]=None, bg_color:tuple[int, int, int]=None):
        """
        Writes text to the terminal.

        Args:
            text (bytes): Terminal output to write.
            fg_color (tuple[int, int, int], optional): RGB foreground color.
            bg_color (tuple[int, int, int], optional): RGB background color.
        """
        with self.lock:
            # fg
            if not fg_color is None:
                os.write(self.stdout_FDI.real_fd, f"\033[38;2;{fg_color[0]};{fg_color[1]};{fg_color[2]}m".encode())
            # bg
            if not bg_color is None:
                os.write(self.stdout_FDI.real_fd, f"\033[48;2;{bg_color[0]};{bg_color[1]};{bg_color[2]}m".encode())

            # write
            os.write(self.stdout_FDI.real_fd, text)

            # reset color
            os.write(self.stdout_FDI.real_fd, f"\033[0m".encode())

    def close(self):
        """
        Finalizes the terminal UI session.

        Moves the cursor to the bottom-most rendered tile region to avoid
        leaving the cursor inside a UI block, restores the terminal cursor
        visibility, and shuts down the stdout FDInterceptor cleanly.
        """
        if self.isAlive():
            maxY = max(e.y + e.height for e in self.tiles)
            self.write(f"\x1b[{maxY};{1}H".encode())

            self.showCursor()
            # kill threads
            self.exit.set()
            self.stdout_FDI.close()