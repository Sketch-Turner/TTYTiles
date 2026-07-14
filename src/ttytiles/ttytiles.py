import os
import sys
import threading
from collections import deque
import queue
import time

if os.name == "nt":
    import msvcrt
else:
    import tty
    import termios
    import select

class TerminalTiler:
    """
    Manages a collection of Tiles to build a structured
    terminal UI layout.

    Provides functionality for creating, positioning, and updating
    multiple independent terminal regions, each with its
    own border, header, and text buffer.
    """

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
        KEY_CTRL_X = "CTRL_x"

        KEY_ANY = "ANY"

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
                        "H": self.KEY_UP,
                        "P": self.KEY_DOWN,
                        "K": self.KEY_LEFT,
                        "M": self.KEY_RIGHT,
                        "S": self.KEY_DELETE,
                        "G": self.KEY_HOME,
                        "O": self.KEY_END,
                        "I": self.KEY_PAGE_UP,
                        "Q": self.KEY_PAGE_DOWN,
                    }.get(code, code)

                if ch == "\r":
                    return self.KEY_ENTER

                if ch == "\t":
                    return self.KEY_TAB

                if ch == "\x08":
                    return self.KEY_BACKSPACE

                if ch == "\x1b":
                    return self.KEY_ESCAPE

                if ch == "\x03":
                    return self.KEY_CTRL_C

                if ch == "\x18":
                    return self.KEY_CTRL_X

                return ch

            else:
                fd = sys.stdin.fileno()

                old = termios.tcgetattr(fd)

                try:
                    tty.setraw(fd)

                    ch = os.read(fd, 1)

                    # Ctrl+C
                    if ch == b"\x03":
                        return self.KEY_CTRL_C
                    
                    if ch == b"\x18":
                        return self.KEY_CTRL_X

                    # Escape / escape sequences
                    if ch == b"\x1b":
                        seq = b"\x1b"

                        while True:
                            r, _, _ = select.select([fd], [], [], 0.01)

                            if not r:
                                break

                            seq += os.read(fd, 1)

                        return {
                            b"\x1b[A": self.KEY_UP,
                            b"\x1b[B": self.KEY_DOWN,
                            b"\x1b[C": self.KEY_RIGHT,
                            b"\x1b[D": self.KEY_LEFT,

                            b"\x1b[H": self.KEY_HOME,
                            b"\x1b[F": self.KEY_END,

                            b"\x1bOH": self.KEY_HOME,  # xterm variant
                            b"\x1bOF": self.KEY_END,

                            b"\x1b[3~": self.KEY_DELETE,

                            b"\x1b[5~": self.KEY_PAGE_UP,
                            b"\x1b[6~": self.KEY_PAGE_DOWN,
                        }.get(seq, self.KEY_ESCAPE)

                    if ch in (b"\r", b"\n"):
                        return self.KEY_ENTER

                    if ch == b"\t":
                        return self.KEY_TAB

                    if ch in (b"\x7f", b"\x08"):
                        return self.KEY_BACKSPACE

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
            return s in TerminalTiler.Keyboard.PRINTABLE

    class FDInterceptor:
        """
        Intercepts writes to a file descriptor using an OS pipe and forwards captured 
        output lines to a user-defined callback function in a background thread.
        """
        def __init__(self, fd:int, exit_event:threading.Event, wait_con:threading.Condition):
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
            self.wait_con = wait_con

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

            with self.wait_con:
                self.wait_con.notify_all()

    class Header:
        """
        Stores and manages a fixed-size collection of text lines for
        terminal-style header rendering, with optional text wrapping
        and border support.
        """

        def __init__(self,
            lines:int=0,
            textWrap:int=0, textJust:int=0,
            colorFG:tuple[int, int, int]=None, colorBG:tuple[int, int, int]=None,
            colorFG_F:tuple[int, int, int]=None, colorBG_F:tuple[int, int, int]=None):
            """
            Initializes the header buffer and display configuration.

            Args:
                lines (int): Maximum number of text rows stored.
                textWrap (int): Text wrap mode. Style.Wrap.WRAP or Style.Wrap.NOWRAP.
                textJust (int): Text justify mode. Style.Justify.LJUST, Style.Justify.CENTERED, or Style.Justify.RJUST.
                colorFG (tuple[int, int, int], optional): Text foreground RGB color.
                colorBG (tuple[int, int, int], optional): Text background RGB color.
                colorFG_F (tuple[int, int, int], optional): Focused text foreground RGB color. Defaults to `colorFG`.
                colorBG_F (tuple[int, int, int], optional): Focused text background RGB color. Defaults to `colorBG`.
            """
            self.textWrap = textWrap if textWrap in TerminalTiler.Style.Wrap.STYLES else TerminalTiler.Style.Wrap.NOWRAP
            self.textJust = textJust if textJust in TerminalTiler.Style.Justify.STYLES else TerminalTiler.Style.Justify.LJUST
            self.colorFG = colorFG
            self.colorBG = colorBG
            self.colorFG_F = colorFG_F if colorFG_F is not None else colorFG
            self.colorBG_F = colorBG_F if colorBG_F is not None else colorBG

            # text
            self.rows = lines
            self.text = deque(maxlen=self.rows)

        def resize(self, lines:int):
            """
            Resize header text buffer to given size.
            """
            self.rows = lines
            self.text = deque(self.text, maxlen=lines)

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

            def canMerge(self, other:"TerminalTiler.Border.Charset")->bool:
                """
                Determines whether this border character set can be merged with another.

                Args:
                    other (Border.CharSet): The character set to compare against.

                Returns:
                    bool: ``True`` if the two character sets can be merged safely, otherwise ``False``.
                """
                return (
                    self.junctionAll == other.junctionAll and
                    self.junctionHN == other.junctionHN and
                    self.junctionHS == other.junctionHS and
                    self.junctionVE == other.junctionVE and
                    self.junctionVW == other.junctionVW and
                    self.lineH == other.lineH and
                    self.lineV == other.lineV
                )

        NO_BORDER = 0
        CUSTOM = 1
        SINGLE_BOX = 2
        DOUBLE_BOX = 3
        HEAVY_BOX = 4
        ASCII = 5
        ASCII_ALT = 6
        BORDER_STYLES = {NO_BORDER, CUSTOM, SINGLE_BOX, DOUBLE_BOX, HEAVY_BOX, ASCII, ASCII_ALT}
        BORDER_CHARS = {NO_BORDER:  "",
                        CUSTOM:     "",
                        SINGLE_BOX: "─│┌┐└┘├┤┬┴┼▄▀█▲▼⯇⯈",
                        DOUBLE_BOX: "═║╔╗╚╝╠╣╦╩╬▄▀█▲▼⯇⯈",
                        HEAVY_BOX:  "━┃┏┓┗┛┣┫┳┻╋▄▀█▲▼⯇⯈",
                        ASCII:      "-|+++++++++###^v<>",
                        ASCII_ALT:  "=|*********###^v<>"
                        }

        def __init__(self,
            style:int=None, charset:str=None,
            colorFG:tuple[int, int, int]=None, colorBG:tuple[int, int, int]=None,
            style_F:int=None, charset_F:str=None,
            colorFG_F:tuple[int, int, int]=None, colorBG_F:tuple[int, int, int]=None):
            """
            Border constructor. If any focused attributes are not set, the default border attribute will be used.

            Args:
                style (int): Border style.
                charset (str): Custom border character(s). If this is not None, border.style is set to CUSTOM.
                colorFG (tuple[int, int, int]): Border foreground RGB color.
                colorBG (tuple[int, int, int]): Border background RGB color.
                style_F (int): Border style when focused.
                charset_F (str): Border charset when focused.
                colorFG_F (tuple[int, int, int]): Border foreground RGB color when focused.
                colorBG_F (tuple[int, int, int]): Border background RGB color when focused.
            """
            # normal border
            if charset is None:
                self.style = style if style in self.BORDER_STYLES else self.NO_BORDER
                charset = self.BORDER_CHARS[self.style]
            else:
                self.style = self.CUSTOM

            self.charset = self.Charset(charset)
            self.colorFG = colorFG
            self.colorBG = colorBG

            # focused border
            if charset_F is None:
                self.style_F = (
                    style_F if style_F in self.BORDER_STYLES else self.NO_BORDER
                ) if style_F is not None else self.style

                charset_F = self.BORDER_CHARS[self.style_F]
            else:
                self.style_F = self.CUSTOM

            self.charset_F = self.Charset(charset_F) if charset_F is not None else self.Charset(charset)
            self.colorFG_F = colorFG_F if colorFG_F is not None else colorFG
            self.colorBG_F = colorBG_F if colorBG_F is not None else colorBG

        def getTop(self, width:int, focused:bool)->str:
            """
            Returns the top border line for the specified width.

            Args:
                width (int): Total width of the border line.
                focused (bool): Is the tile focused?

            Returns:
                str: Rendered top border string.
            """
            if focused:
                return self.charset_F.cornerNW + self.charset_F.lineH * (width - 2) + self.charset_F.cornerNE
            else:
                return self.charset.cornerNW + self.charset.lineH * (width - 2) + self.charset.cornerNE

        def getMiddle(self, width:int, focused:bool):
            """
            Returns the middle separator border line for the specified width.

            Args:
                width (int): Total width of the border line.
                focused (bool): Is the tile focused?

            Returns:
                str: Rendered middle border string.
            """
            if focused:
                return self.charset_F.junctionVE + self.charset_F.lineH * (width - 2) + self.charset_F.junctionVW
            else:
                return self.charset.junctionVE + self.charset.lineH * (width - 2) + self.charset.junctionVW

        def getBottom(self, width:int, focused:bool):
            """
            Returns the bottom border line for the specified width.

            Args:
                width (int): Total width of the border line.
                focused (bool): Is the tile focused?

            Returns:
                str: Rendered bottom border string.
            """
            if focused:
                return self.charset_F.cornerSW + self.charset_F.lineH * (width - 2) + self.charset_F.cornerSE
            else:
                return self.charset.cornerSW + self.charset.lineH * (width - 2) + self.charset.cornerSE

    class Style:
        class Wrap:
            """
            Text wrapping.

            STYLES:
            - NOWRAP
            - WRAP
            - WORD_WRAP
            """
            NOWRAP = 0
            WRAP = 1
            WORD_WRAP = 2
            STYLES = {NOWRAP, WRAP, WORD_WRAP}

        class Justify:
            """
            Text justification.

            STYLES:
            - LJUST
            - CENTERED
            - RJUST
            """
            LJUST = 0
            CENTERED = 1
            RJUST = 2
            STYLES = {LJUST, CENTERED, RJUST}

        class Size:
            """
            Text display.

            STYLES:
            - FIXED
            - SCROLLING
            """
            FIXED = 0
            SCROLLING = 1
            STYLES = {FIXED, SCROLLING}

    class DisplayTile:
        """
        A terminal UI region that renders a bordered rectangular tile
        with an optional header and scrollable/wrappable text buffer.
        """
        def __init__(self, write_func, merge_func,
            x:int, y:int, width:int, height:int,
            visible:bool, canFocus:bool,
            textWrap:int, textJust:int, sizeMode:int,
            border:"TerminalTiler.Border",
            header:"TerminalTiler.Header",
            colorFG:tuple[int, int, int], colorBG:tuple[int, int, int], colorFG_F:tuple[int, int, int], colorBG_F:tuple[int, int, int]):
            """
            Initializes a display tile.

            Configures the tile geometry, visibility, text layout, colors, border,
            and optional header used to render a region of the terminal.

            Args:
                write_func: Function used to write text to the terminal.
                merge_func: Function used to merge borders.
                x (int): Tile origin column (1-based).
                y (int): Tile origin row (1-based).
                width (int): Tile width in characters.
                height (int): Tile height in rows.
                visible (bool): Whether the tile is initially visible.
                canFocus (bool): Whether the tile can receive keyboard focus.

                textWrap (int): Text wrapping mode. Style.Wrap.WRAP or Style.Wrap.NOWRAP.
                textJust (int): Text justification mode. Style.Justify.LJUST, Style.Justify.CENTERED, or Style.Justify.RJUST.
                sizeMode (int): Text buffer sizing mode. Style.Size.FIXED or Style.Size.SCROLLING.

                border (TerminalTiler.Border): Border configuration.
                header (TerminalTiler.Header): Header configuration.

                colorFG (tuple[int, int, int]): Text foreground RGB color.
                colorBG (tuple[int, int, int]): Text background RGB color.
                colorFG_F (tuple[int, int, int]): Focused text foreground RGB color.
                colorBG_F (tuple[int, int, int]): Focused text background RGB color.
            """
            self.mutate = threading.RLock()
            self.x = x #col
            self.y = y #row
            self.width = width 
            self.height = height 
            self.textWrap = textWrap if textWrap in TerminalTiler.Style.Wrap.STYLES else TerminalTiler.Style.Wrap.NOWRAP
            self.textJust = textJust if textJust in TerminalTiler.Style.Justify.STYLES else TerminalTiler.Style.Justify.LJUST
            self.sizeMode = sizeMode if sizeMode in TerminalTiler.Style.Size.STYLES else TerminalTiler.Style.Size.FIXED
            self.border = border
            self.header = header
            self.write = write_func
            self.mergeBorder = merge_func

            # colors
            self.colorFG = colorFG
            self.colorBG = colorBG
            self.colorFG_F = colorFG_F
            self.colorBG_F = colorBG_F

            # set size of buffers
            self.text = []
            self.resize()

            self.visible = visible
            self.focused = False
            self.canFocus = canFocus
            if self.visible:
                self.show()

        def getRect(self)->tuple[int, int, int, int]:
            """
            Returns the tile's bounding rectangle.

            Returns:
                tuple[int, int, int, int]: The rectangle as
                ``(x1, y1, x2, y2)``, where:
                    - ``x1`` is the left edge.
                    - ``y1`` is the top edge.
                    - ``x2`` is the right edge (inclusive).
                    - ``y2`` is the bottom edge (inclusive).
            """
            return (
                self.x,
                self.y,
                self.x + self.width - 1,
                self.y + self.height - 1
            )

        def clear(self):
            """
            Clears the text buffer.
            """
            with self.mutate:
                self.text.clear()
                self.tIndex = 0
                if self.visible:
                    self.show()

        def clearHeader(self):
            """
            Clears the header text buffer.
            """
            with self.mutate:
                self.header.text.clear()
                if self.visible:
                    self.show()

        def resize(self, width:int=None, height:int=None):
            """
            Resize the display tile and recalculate all derived layout values.

            Updates the tile's dimensions and recomputes the positions and sizes of
            the text area, header, and borders. The usable text region is adjusted
            based on the configured border style, header, and size mode.
            Resets the scroll index to the top.

            Args:
                width (int, optional):
                    New width of the tile. If `None`, the `self.width` is used.
                height (int, optional):
                    New height of the tile. If `None`, the `self.height` is used.
            """
            with self.mutate:
                if width:
                    self.width = width
                if height:
                    self.height = height

                # text
                self.rows = self.height - self.header.rows
                self.cols = self.width
                self.tx = self.x
                self.ty = self.y + self.header.rows
                self.hx = self.x
                self.hy = self.y
                if self.border.style != TerminalTiler.Border.NO_BORDER:
                    self.tx += 1
                    self.ty += 1
                    self.rows -= 2
                    self.cols -= 2
                    self.hx += 1
                    self.hy += 1

                if self.header.rows > 0:
                    self.ty += 1
                    self.rows -= 1

                if self.sizeMode == TerminalTiler.Style.Size.SCROLLING:
                    self.cols -= 2

                if self.sizeMode == TerminalTiler.Style.Size.FIXED:
                    self.text = deque(self.text, maxlen=self.rows)
                else:
                    self.text = list(self.text)

                self.tIndex = 0

        def drawBorder(self):
            """
            Draws:
                - Left and right vertical border lines
                - Top border line
                - Optional header separator (middle border)
                - Bottom border line
            """
            with self.mutate:
                if self.border.style != TerminalTiler.Border.NO_BORDER:
                    if self.focused:
                        color_fg = self.border.colorFG_F
                        color_bg = self.border.colorBG_F
                        charset = self.border.charset_F
                    else:
                        color_fg = self.border.colorFG
                        color_bg = self.border.colorBG
                        charset = self.border.charset

                    for row in range(self.y + 1, self.y + self.height - 1):
                        self.write(f"\x1b[{row};{self.x}H{charset.lineV}".encode(), color_fg, color_bg)
                        self.write(f"\x1b[{row};{self.x + self.width - 1}H{charset.lineV}".encode(), color_fg, color_bg)

                    self.write(f"\x1b[{self.y};{self.x}H{self.border.getTop(self.width, self.focused)}".encode(), color_fg, color_bg)
                    if self.header.rows > 0:
                        self.write(f"\x1b[{self.y + self.header.rows + 1};{self.x}H{self.border.getMiddle(self.width, self.focused)}".encode(), color_fg, color_bg)
                    self.write(f"\x1b[{self.y + self.height - 1};{self.x}H{self.border.getBottom(self.width, self.focused)}".encode(), color_fg, color_bg)

                    if self.mergeBorder:
                        self.mergeBorder(self)

                    if self.sizeMode == TerminalTiler.Style.Size.SCROLLING:
                        self.drawScrollbarBorder()
                        self.drawScrollbar()

        def drawScrollbarBorder(self):
            """
            Draws the right-side scrollbar border.
            """
            with self.mutate:
                if self.focused:
                    color_fg = self.border.colorFG_F
                    color_bg = self.border.colorBG_F
                    charset = self.border.charset_F
                else:
                    color_fg = self.border.colorFG
                    color_bg = self.border.colorBG
                    charset = self.border.charset

                #top
                header_height = self.header.rows
                cornerTop = charset.cornerNE
                if self.header.rows > 0:
                    header_height += 1
                    cornerTop = charset.junctionVW
                self.write(f"\x1b[{self.y + header_height};{self.x + self.width - 3}H{charset.junctionHS + charset.lineH + cornerTop}".encode(), color_fg, color_bg)

                #middle
                for row in range(self.y + header_height + 1, self.y + self.height - 1):
                    self.write(f"\x1b[{row};{self.x + self.width - 3}H{charset.lineV + ' ' + charset.lineV}".encode(), color_fg, color_bg)

                #bottom
                cornerBottom = charset.cornerSW
                if self.border.style != TerminalTiler.Border.NO_BORDER:
                    cornerBottom = charset.junctionHN
                self.write(f"\x1b[{self.y + self.height - 1};{self.x + self.width - 3}H{cornerBottom + charset.lineH + charset.cornerSE}".encode(), color_fg, color_bg)

        def drawScrollbar(self):
            """
            Renders the scrollbar thumb inside the scrollbar track.
            """
            with self.mutate:
                if self.focused:
                    color_fg = self.border.colorFG_F
                    color_bg = self.border.colorBG_F
                    charset = self.border.charset_F
                else:
                    color_fg = self.border.colorFG
                    color_bg = self.border.colorBG
                    charset = self.border.charset

                bar_top = self.y + self.header.rows
                if self.border.style != TerminalTiler.Border.NO_BORDER:
                    bar_top += 1
                if self.header.rows > 0:
                    bar_top += 1

                # clear
                for row in range(bar_top, self.y + self.height - 1):
                    self.write(f"\x1b[{row};{self.x + self.width - 2}H ".encode(), color_fg, color_bg)

                # calc bar position
                max_scroll = max(len(self.text) - self.rows, 1)
                bar_offset = self.tIndex * (self.rows - 1) / max_scroll

                if self.border.style == TerminalTiler.Border.ASCII:
                    bar_offset = round(bar_offset)
                else:
                    bar_offset = round(bar_offset * 2) / 2

                if bar_offset > (self.rows - 1):
                    bar_offset = self.rows - 1

                bar1 = int(bar_offset)
                bar2 = int(bar_offset + 0.5)

                # draw
                if bar1 == bar2:
                    self.write(f"\x1b[{bar_top + bar1};{self.x + self.width - 2}H{charset.boxFull}".encode(), color_fg, color_bg)
                else:
                    self.write(f"\x1b[{bar_top + bar1};{self.x + self.width - 2}H{charset.boxLower}".encode(), color_fg, color_bg)
                    self.write(f"\x1b[{bar_top + bar2};{self.x + self.width - 2}H{charset.boxUpper}".encode(), color_fg, color_bg)

        def drawText(self):
            """
            Renders the visible portion of the text buffer to the terminal.
            """
            with self.mutate:
                if self.focused:
                    color_fg = self.colorFG_F
                    color_bg = self.colorBG_F
                else:
                    color_fg = self.colorFG
                    color_bg = self.colorBG
                row = self.ty
                start = max(0, min(self.tIndex, len(self.text) - self.rows))
                lines = list(self.text)[start:start + self.rows]
                if len(lines) < self.rows:
                    lines += [' ' * self.cols] * (self.rows - len(lines))
                for line in lines:
                    self.write(f"\x1b[{row};{self.tx}H{line}".encode(), color_fg, color_bg)
                    row += 1

        def justify(self, text:str, textJust:int, width:int)->str:
            """
            Justify text within a fixed-width field.

            Args:
                text (str):
                    The text to justify.
                textJust (int):
                    The justification mode. Style.Justify.LJUST, Style.Justify.CENTERED, or Style.Justify.RJUST.
                width (int):
                    The total width of the output string.

            Returns:
                str:
                    The justified string.
            """
            if textJust == TerminalTiler.Style.Justify.LJUST:
                return text + ' ' * (width - len(text))
            elif textJust == TerminalTiler.Style.Justify.CENTERED:
                extra = width - len(text)
                left = extra // 2
                right = extra - left
                return (' ' * left) + text + (' ' * right)
            elif textJust == TerminalTiler.Style.Justify.RJUST:
                return ' ' * (width - len(text)) + text

        def update(self, text:str):
            """
            Appends new text to the tile's internal buffer and renders
            the visible text region in the terminal.

            Args:
                text (str): Text to add to text buffer.
            """
            with self.mutate:
                text = str(text).replace('\r\n', '\n').replace('\r', '\n')
                for line in text.split('\n'):
                    if self.textWrap == TerminalTiler.Style.Wrap.NOWRAP:
                        output = line[:self.cols]
                        self.text.append(self.justify(output, self.textJust, self.cols))
                    elif self.textWrap == TerminalTiler.Style.Wrap.WRAP:
                        for i in range(0, len(line), self.cols):
                            output = line[i:i+self.cols]
                            self.text.append(self.justify(output, self.textJust, self.cols))
                    elif self.textWrap == TerminalTiler.Style.Wrap.WORD_WRAP:
                        if len(line) == 0:
                            self.text.append(self.justify(line, self.textJust, self.cols))
                            continue
                        pos = 0
                        while pos < len(line):
                            end = min(pos + self.cols, len(line))

                            # wrap on whitespace.
                            if end < len(line):
                                split = line.rfind(" ", pos, end)
                                if split > pos:
                                    output = line[pos:split]
                                    pos = split + 1
                                else:
                                    output = line[pos:end]
                                    pos = end
                            else:
                                output = line[pos:end]
                                pos = end

                            self.text.append(self.justify(output, self.textJust, self.cols))

                self.tIndex = len(self.text) - 1

                if self.visible:
                    # write text
                    self.drawText()

                    # update scrollbar position
                    if self.sizeMode == TerminalTiler.Style.Size.SCROLLING:
                        self.drawScrollbar()

        def updateHeader(self, text:str):
            """
            Appends new text to the tile's header buffer and renders
            the visible header region in the terminal.

            Args:
                text (str): Text to add to text buffer.
            """
            with self.mutate:
                cols = self.cols if self.sizeMode != TerminalTiler.Style.Size.SCROLLING else self.cols + 2
                text = str(text).replace('\r\n', '\n').replace('\r', '\n')
                for line in text.split('\n'):
                    if self.textWrap == TerminalTiler.Style.Wrap.NOWRAP:
                        output = line[:cols]
                        self.header.text.append(self.justify(output, self.header.textJust, cols))
                    elif self.textWrap == TerminalTiler.Style.Wrap.WRAP:
                        for i in range(0, len(line), cols):
                            output = line[i:i+cols]
                            self.header.text.append(self.justify(output, self.header.textJust, cols))
                    elif self.textWrap == TerminalTiler.Style.Wrap.WORD_WRAP:
                        if len(line) == 0:
                            self.text.append(self.justify(line, self.textJust, self.cols))
                            continue
                        pos = 0
                        while pos < len(line):
                            end = min(pos + cols, len(line))

                            # wrap on whitespace.
                            if end < len(line):
                                split = line.rfind(" ", pos, end)
                                if split > pos:
                                    output = line[pos:split]
                                    pos = split + 1
                                else:
                                    output = line[pos:end]
                                    pos = end
                            else:
                                output = line[pos:end]
                                pos = end

                            self.header.text.append(self.justify(output, self.header.textJust, cols))

                if self.visible:
                    self.drawHeader()

        def drawHeader(self):
            """
            Renders header to terminal.
            """
            if self.header.rows > 0:
                if self.focused:
                    color_fg = self.header.colorFG_F
                    color_bg = self.header.colorBG_F
                else:
                    color_fg = self.header.colorFG
                    color_bg = self.header.colorBG
                row = self.hy
                lines = self.header.text
                cols = self.cols if self.sizeMode != TerminalTiler.Style.Size.SCROLLING else self.cols + 2
                if len(lines) < self.header.rows:
                    lines += [' ' * cols] * (self.rows - len(lines))
                for line in lines:
                    self.write(f"\x1b[{row};{self.hx}H{line}".encode(), color_fg, color_bg)
                    row += 1

        def handleInput(self, key:str):
            """
            Handles keyboard input to DisplayTile.

            Args:
                key (str): Key pressed.
            """
            if self.sizeMode == TerminalTiler.Style.Size.SCROLLING:
                if key == TerminalTiler.Keyboard.KEY_UP:
                    top = max(0, min(self.tIndex, len(self.text) - self.rows))
                    if top > 0:
                        self.tIndex = top - 1
                        # text
                        self.drawText()

                        # scrollbar
                        self.drawScrollbar()

                elif key == TerminalTiler.Keyboard.KEY_DOWN:
                    bottom = max(0, min(self.tIndex, len(self.text) - self.rows))
                    if bottom < len(self.text) - self.rows:
                        self.tIndex = bottom + 1
                        # text
                        self.drawText()

                        # scrollbar
                        self.drawScrollbar()
                
                elif key == TerminalTiler.Keyboard.KEY_PAGE_UP:
                    top = max(0, min(self.tIndex, len(self.text) - self.rows))
                    if top > 0:
                        self.tIndex = 0
                        # text
                        self.drawText()

                        # scrollbar
                        self.drawScrollbar()

                elif key == TerminalTiler.Keyboard.KEY_PAGE_DOWN:
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
            with self.mutate:
                self.visible = True
                # hide cursor
                self.write("\033[?25l".encode())
                self.drawBorder()
                self.drawHeader()
                self.drawText()

        def hide(self):
            """
            Hides DisplayTile
            """
            with self.mutate:
                self.visible = False
                # hide cursor
                self.write("\033[?25l".encode())
                for i in range(self.height):
                    self.write(f"\x1b[{self.y + i};{self.x}H{' ' * self.width}".encode())

        def dump(self)->str:
            """
            Dump lines of DisplayTile.text joined with newline. All whitespace is stripped.

            Returns:
                str: DisplayTile text.
            """
            with self.mutate:
                return "\n".join([text.strip() for text in list(self.text)])

        def setColor(self, colors:dict[str, tuple[int, int, int]]=None):
            """
            Sets the colors used to render the tile, border, and header.

            If `colors` is ``None``, all colors are reset to None.

            The `colors` dictionary may contain any combination of the following keys:

                Text:
                    - "TEXT_FG"     : Text foreground color
                    - "TEXT_BG"     : Text background color
                    - "TEXT_FG_F"   : Focused text foreground color
                    - "TEXT_BG_F"   : Focused text background color

                Border:
                    - "BORDER_FG"   : Border foreground color
                    - "BORDER_BG"   : Border background color
                    - "BORDER_FG_F" : Focused border foreground color
                    - "BORDER_BG_F" : Focused border background color

                Header:
                    - "HEADER_FG"   : Header foreground color
                    - "HEADER_BG"   : Header background color
                    - "HEADER_FG_F" : Focused header foreground color
                    - "HEADER_BG_F" : Focused header background color

            Each color must be an RGB tuple of the form ``(R, G, B)``, where each
            component is an integer in the range 0-255.

            Args:
                colors: Dictionary mapping color names to RGB tuples. Unspecified
                    colors are left unchanged. If ``None``, all colors are reset.
            """
            with self.mutate:
                if colors is None:
                    self.colorFG = None
                    self.colorBG = None
                    self.colorFG_F = None
                    self.colorBG_F = None

                    self.border.colorFG = None
                    self.border.colorBG = None
                    self.border.colorFG_F = None
                    self.border.colorBG_F = None

                    self.header.colorFG = None
                    self.header.colorBG = None
                    self.header.colorFG_F = None
                    self.header.colorBG_F = None

                else:
                    for k, v in colors.items():
                        if k == "TEXT_FG":
                            self.colorFG = v
                        elif k == "TEXT_BG":
                            self.colorBG = v
                        elif k == "TEXT_FG_F":
                            self.colorFG_F = v
                        elif k == "TEXT_BG_F":
                            self.colorBG_F = v

                        elif k == "BORDER_FG":
                            self.border.colorFG = v
                        elif k == "BORDER_BG":
                            self.border.colorBG = v
                        elif k == "BORDER_FG_F":
                            self.border.colorFG_F = v
                        elif k == "BORDER_BG_F":
                            self.border.colorBG_F = v

                        elif k == "HEADER_FG":
                            self.header.colorFG = v
                        elif k == "HEADER_BG":
                            self.header.colorBG = v
                        elif k == "HEADER_FG_F":
                            self.header.colorFG_F = v
                        elif k == "HEADER_BG_F":
                            self.header.colorBG_F = v

                if self.visible:
                    self.show()

    class InputTile:
        """
        A fixed-size terminal input tile supporting interactive text editing.
        """
        def __init__(self, write_func, merge_func, exit_event:threading.Event,
            x:int, y:int, width:int, height:int,
            visible:bool,
            inputFG:tuple[int, int, int], inputBG:tuple[int, int, int], inputFG_F:tuple[int, int, int], inputBG_F:tuple[int, int, int],
            prompt:str,
            promptFG:tuple[int, int, int], promptBG:tuple[int, int, int], promptFG_F:tuple[int, int, int], promptBG_F:tuple[int, int, int],
            border:"TerminalTiler.Border"):
            """
            Initializes a terminal input field.

            Configures the input field geometry, visibility, prompt, colors, and
            border used to render and interact with the control.

            Args:
                write_func: Function used to write text to the terminal.
                merge_func: Function used to merge borders.
                exit_event (threading.Event): Event used to signal application shutdown.
                x (int): Input field origin column (1-based).
                y (int): Input field origin row (1-based).
                width (int): Input field width in characters.
                height (int): Input field height in rows.
                visible (bool): Whether the input field is initially visible.

                inputFG (tuple[int, int, int]): Input foreground RGB color.
                inputBG (tuple[int, int, int]): Input background RGB color.
                inputFG_F (tuple[int, int, int]): Focused input foreground RGB color.
                inputBG_F (tuple[int, int, int]): Focused input background RGB color.

                prompt (str): Prompt displayed before the input text.

                promptFG (tuple[int, int, int]): Prompt foreground RGB color.
                promptBG (tuple[int, int, int]): Prompt background RGB color.
                promptFG_F (tuple[int, int, int]): Focused prompt foreground RGB color.
                promptBG_F (tuple[int, int, int]): Focused prompt background RGB color.

                border (TerminalTiler.Border): Border configuration for the input field.
            """
            self.mutate = threading.RLock()
            self.exit = exit_event
            self.write = write_func
            self.mergeBorder = merge_func
            self.x = x #col
            self.y = y #row
            self.width = width 
            self.height = height 

            # colors
            self.inputFG = inputFG
            self.inputBG = inputBG
            self.inputFG_F = inputFG_F
            self.inputBG_F = inputBG_F

            self.promptFG = promptFG
            self.promptBG = promptBG
            self.promptFG_F = promptFG_F
            self.promptBG_F = promptBG_F

            # border
            self.border = border

            # build
            self.resize()
            self.setPrompt(prompt)

            self.buffer = []
            self.input = queue.Queue()
            self.visible = visible
            self.focused = False
            self.canFocus = True
            if self.visible:
                self.show()

        def resize(self, width:int=None, height:int=None):
            """
            Resize the display tile and recalculate all derived layout values.

            Updates the tile's dimensions and recomputes the positions and sizes of
            the text area, header, and borders. The usable text region is adjusted
            based on the configured border style, header, and size mode.
            Resets the scroll index to the top.

            Args:
                width (int, optional):
                    New width of the tile. If `None`, the `self.width` is used.
                height (int, optional):
                    New height of the tile. If `None`, the `self.height` is used.
            """
            with self.mutate:
                if width:
                    self.width = width
                if height:
                    self.height = height

                # text
                self.rows = self.height
                self.cols = self.width
                self.tx = self.x
                self.ty = self.y
                if self.border.style != TerminalTiler.Border.NO_BORDER:
                    self.tx += 1
                    self.ty += 1
                    self.rows -= 2
                    self.cols -= 2

        def getRect(self):
            """
            Returns the tile's bounding rectangle.

            Returns:
                tuple[int, int, int, int]: The rectangle as
                ``(x1, y1, x2, y2)``, where:
                    - ``x1`` is the left edge.
                    - ``y1`` is the top edge.
                    - ``x2`` is the right edge (inclusive).
                    - ``y2`` is the bottom edge (inclusive).
            """
            return (
                self.x,
                self.y,
                self.x + self.width - 1,
                self.y + self.height - 1
            )

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
            with self.mutate:
                self.prompt = []
                self.pIndex = 0

                promptBuffer = 0
                prompt = str(prompt).replace('\r\n', '\n').replace('\r', '\n')
                for line in prompt.split('\n'):
                    for i in range(0, len(line), self.cols):
                        chunk = line[i:i + self.cols]
                        self.prompt.append(chunk + ' ' * (self.cols - len(chunk)))
                        promptBuffer = self.cols - len(chunk)

                self.prompt = self.prompt[:self.rows]
                self.py = self.ty + max(len(self.prompt) - 1, 0)
                self.px = self.tx - promptBuffer
                self.px += len(self.prompt[-1]) if len(self.prompt) > 0 else 0

                self.cursorX = self.px
                self.cursorY = self.py
                self.bufferMax = (self.rows - max(1, len(self.prompt))) * self.cols + (self.cols - (self.px - self.tx)) # max num of chars for input

        def show(self):
            """
            Renders InputTile
            """
            with self.mutate:
                self.visible = True
                self.drawBorder()
                self.drawPrompt()
                cX, cY = self.cursorX, self.cursorY
                self.cursorX = self.px
                self.cursorY = self.py
                self.drawInput()
                # move cursor
                self.cursorX = cX
                self.cursorY = cY
                self.write(f"\033[{self.cursorY};{self.cursorX}H".encode())

        def hide(self):
            """
            Hides InputTile
            """
            with self.mutate:
                self.visible = False
                for i in range(self.height):
                    self.write(f"\x1b[{self.y + i};{self.x}H{' ' * self.width}".encode())

        def drawPrompt(self):
            """
            Renders prompt to terminal.
            """
            with self.mutate:
                # render text
                if self.focused:
                    color_fg = self.promptFG_F
                    color_bg = self.promptBG_F
                else:
                    color_fg = self.promptFG
                    color_bg = self.promptBG
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
            with self.mutate:
                if self.border.style != TerminalTiler.Border.NO_BORDER:
                    if self.focused:
                        color_fg = self.border.colorFG_F
                        color_bg = self.border.colorBG_F
                        charset = self.border.charset_F
                    else:
                        color_fg = self.border.colorFG
                        color_bg = self.border.colorBG
                        charset = self.border.charset

                    for row in range(self.y + 1, self.y + self.height - 1):
                        self.write(f"\x1b[{row};{self.x}H{charset.lineV}".encode(), color_fg, color_bg)
                        self.write(f"\x1b[{row};{self.x + self.width - 1}H{charset.lineV}".encode(), color_fg, color_bg)

                    self.write(f"\x1b[{self.y};{self.x}H{self.border.getTop(self.width, self.focused)}".encode(), color_fg, color_bg)
                    self.write(f"\x1b[{self.y + self.height - 1};{self.x}H{self.border.getBottom(self.width, self.focused)}".encode(), color_fg, color_bg)

                    if self.mergeBorder:
                        self.mergeBorder(self)

        def drawInput(self):
            """
            Renders input field.
            """
            with self.mutate:
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
                    color_fg = self.inputFG_F
                    color_bg = self.inputBG_F
                else:
                    color_fg = self.inputFG
                    color_bg = self.inputBG

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

        def handleInput(self, key:str):
            """
            Handles keyboard input.
            """
            # hide cursor
            self.write("\033[?25l".encode())

            if key == TerminalTiler.Keyboard.KEY_LEFT:
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

            elif key == TerminalTiler.Keyboard.KEY_RIGHT:
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

            elif key == TerminalTiler.Keyboard.KEY_BACKSPACE:
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

            elif key == TerminalTiler.Keyboard.KEY_DELETE:
                # cannot delete past end of input
                if self.pIndex < len(self.buffer):
                    # remove char at cursor
                    del self.buffer[self.pIndex]

                    # redraw shifted text starting at current cursor
                    self.drawInput()

                    # restore cursor
                    self.write(f"\033[{self.cursorY};{self.cursorX}H".encode())

            elif key == TerminalTiler.Keyboard.KEY_HOME:
                self.pIndex = 0
                self.cursorX = self.px
                self.cursorY = self.py

                # move cursor
                self.write(f"\033[{self.cursorY};{self.cursorX}H".encode())

            elif key == TerminalTiler.Keyboard.KEY_END:
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

            elif key == TerminalTiler.Keyboard.KEY_ESCAPE:
                self.buffer = []
                self.cursorX = self.px
                self.cursorY = self.py
                self.pIndex = 0
                self.drawInput()
                self.write(f"\033[{self.cursorY};{self.cursorX}H".encode())

            elif key == TerminalTiler.Keyboard.KEY_ENTER:
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

            elif TerminalTiler.Keyboard.isPrintable(key) and len(self.buffer) < self.bufferMax:
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

        def setColor(self, colors:dict[str, tuple[int, int, int]]=None):
            """
            Sets the colors used to render the tile, border, and header.

            If `colors` is ``None``, all colors are reset to None.

            The `colors` dictionary may contain any combination of the following keys:

                Prompt:
                    - "PROMPT_FG"   : Prompt foreground color
                    - "PROMPT_BG"   : Prompt background color
                    - "PROMPT_FG_F" : Focused prompt foreground color
                    - "PROMPT_BG_F" : Focused prompt background color

                Input:
                    - "INPUT_FG"    : Input foreground color
                    - "INPUT_BG"    : Input background color
                    - "INPUT_FG_F"  : Focused input foreground color
                    - "INPUT_BG_F"  : Focused input background color

                Border:
                    - "BORDER_FG"   : Border foreground color
                    - "BORDER_BG"   : Border background color
                    - "BORDER_FG_F" : Focused border foreground color
                    - "BORDER_BG_F" : Focused border background color

            Each color must be an RGB tuple of the form ``(R, G, B)``, where each
            component is an integer in the range 0-255.

            Args:
                colors: Dictionary mapping color names to RGB tuples. Unspecified
                    colors are left unchanged. If ``None``, all colors are reset.
            """
            with self.mutate:
                if colors is None:
                    self.promptFG = None
                    self.promptBG = None
                    self.promptFG_F = None
                    self.promptBG_F = None

                    self.inputFG = None
                    self.inputBG = None
                    self.inputFG_F = None
                    self.inputBG_F = None

                    self.border.colorFG = None
                    self.border.colorBG = None
                    self.border.colorFG_F = None
                    self.border.colorBG_F = None

                else:
                    for k, v in colors.items():
                        if k == "PROMPT_FG":
                            self.promptFG = v
                        elif k == "PROMPT_BG":
                            self.promptBG = v
                        elif k == "PROMPT_FG_F":
                            self.promptFG_F = v
                        elif k == "PROMPT_BG_F":
                            self.promptBG_F = v

                        elif k == "INPUT_FG":
                            self.inputFG = v
                        elif k == "INPUT_BG":
                            self.inputBG = v
                        elif k == "INPUT_FG_F":
                            self.inputFG_F = v
                        elif k == "INPUT_BG_F":
                            self.inputBG_F = v

                        elif k == "BORDER_FG":
                            self.border.colorFG = v
                        elif k == "BORDER_BG":
                            self.border.colorBG = v
                        elif k == "BORDER_FG_F":
                            self.border.colorFG_F = v
                        elif k == "BORDER_BG_F":
                            self.border.colorBG_F = v

                if self.visible:
                    self.show()

    class ProgressBar:
        """
        A terminal UI region that renders a ProgressBar.
        """
        def __init__(self, write_func, merge_func,
            max:int,
            x:int, y:int, width:int, height:int,
            visible:bool,
            border:"TerminalTiler.Border",
            barChar:str, textOverlay:str, textLeft:str, textRight:str,
            colorFG:tuple[int, int, int], colorBG:tuple[int, int, int]):
            """
            Initializes a ProgressBar.

            Configures the ProgressBar geometry, appearance, border, and maximum
            progress value used to determine the completion percentage.

            Args:
                write_func: Function used to write text to the terminal.
                merge_func: Function used to merge borders.
                max (int): Maximum progress value representing 100% completion.
                x (int): ProgressBar origin column (1-based).
                y (int): ProgressBar origin row (1-based).
                width (int): ProgressBar width in characters.
                height (int): ProgressBar height in rows.
                visible (bool): Whether the ProgressBar is initially visible.

                border (TerminalTiler.Border): Border configuration.

                barChar (str): Character used to draw the filled portion of the ProgressBar.
                textOverlay (str): Overlay text is centered within the bar and replaces the underlying bar characters.
                textLeft (str): Rendered on left side of ProgressBar.
                textRight (str): Rendered on right side of ProgressBar.

                colorFG (tuple[int, int, int]): ProgressBar foreground RGB color.
                colorBG (tuple[int, int, int]): ProgressBar background RGB color.
            """
            self.mutate = threading.RLock()
            self.startTime = None
            self.lastUpdateTime = None
            self.averageTime = 0.0
            self.alpha = 0.1 # used for moving avg calc
            self.max = max
            self.value = 0
            self.textLeft = textLeft # text on left side of ProgressBar
            self.textRight = textRight # text on right side of ProgressBar
            self.textOverlay = textOverlay # text overlayed on top of bar
            self.barChar = barChar # char used to draw bar
            self.x = x
            self.y = y
            self.width = width
            self.height = height
            self.canFocus = False
            self.focused = False
            self.visible = visible
            self.displayTile = TerminalTiler.DisplayTile(
                write_func=write_func,
                merge_func=merge_func,
                x=x,
                y=y,
                width=width,
                height=height,
                visible=visible,
                canFocus=False,
                colorFG=colorFG,
                colorBG=colorBG,
                colorFG_F=colorFG,
                colorBG_F=colorBG,
                textWrap=TerminalTiler.Style.Wrap.NOWRAP,
                textJust=TerminalTiler.Style.Justify.LJUST,
                sizeMode=TerminalTiler.Style.Size.FIXED,
                border=border,
                header=TerminalTiler.Header()
            )

            if visible:
                self.show()

        def getRect(self):
            """
            Returns the tile's bounding rectangle.

            Returns:
                tuple[int, int, int, int]: The rectangle as
                ``(x1, y1, x2, y2)``, where:
                    - ``x1`` is the left edge.
                    - ``y1`` is the top edge.
                    - ``x2`` is the right edge (inclusive).
                    - ``y2`` is the bottom edge (inclusive).
            """
            return self.displayTile.getRect()

        def drawBorder(self):
            """
            Render border.
            """
            with self.mutate:
                self.displayTile.drawBorder()

        def drawText(self):
            """
            Render ProgressBar.
            """
            with self.mutate:
                self.displayTile.drawText()

        def show(self):
            """
            Render element. Starts timer.
            """
            with self.mutate:
                self.startTime = time.monotonic()
                self.lastUpdateTime = self.startTime
                self.averageTime = 0.0
                self.visible = True
                self.displayTile.show()

        def hide(self):
            """
            Hide element.
            """
            with self.mutate:
                self.visible = False
                self.displayTile.hide()

        def formatTime(self, seconds:float, fmt:str)->str:
            """
            Format a duration into a compact, human-readable string.

            Supported tokens:
                H   - Hours
                HH  - Zero-padded hours
                M   - Minutes
                MM  - Zero-padded minutes
                S   - Seconds
                SS  - Zero-padded seconds
                m   - Tenths
                mm  - Hundredths
                mmm - Milliseconds

            Args:
                seconds (float): Duration in seconds.
                fmt (str): Format.

            Returns:
                str:
                    The formatted duration string.
            """
            total_ms = int(round(seconds * 1000))

            h, rem = divmod(total_ms, 3_600_000)
            m, rem = divmod(rem, 60_000)
            s, ms = divmod(rem, 1000)

            replacements = {
                "HH": f"{h:02}",
                "H": str(h),
                "MM": f"{m:02}",
                "M": str(m),
                "SS": f"{s:02}",
                "S": str(s),
                "mmm": f"{ms:03}",
                "mm": f"{ms // 10:02}",
                "m": str(ms // 100),
            }

            # Replace longest tokens first
            for token in sorted(replacements, key=len, reverse=True):
                fmt = fmt.replace(token, replacements[token])

            return fmt

        def formatText(self, text:str, mapping:dict)->str:
            """
            Formating helper.

            Args:
                text (str):The text template containing placeholder fields.
                mapping (dict): Dictionary mapping placeholder names to their corresponding values.

            Returns:
                str: The formatted text.
            """
            for key, value in mapping.items():
                while (start := text.find(f"{{{key}")) != -1:
                    end = text.find("}", start)
                    _, _, fmt = text[start + 1:end].partition(":")

                    if key in ("AVG_TIME", "ELAPSED", "REMAINING"):
                        replacement = self.formatTime(value, fmt or "MM:SS")
                    else:
                        replacement = format(value, fmt)

                    text = text[:start] + replacement + text[end + 1:]

            return text

        def update(self, increment:int=1):
            """
            Increment the progress value and redraw the ProgressBar.
            The current value is increased by increment and clamped to the
            configured maximum value. The bar is automatically resized to fit
            within the available tile width after accounting for any surrounding
            text and bar boundaries.

            Three text sections will be rendered if set:

                textLeft    - Rendered on left side of ProgressBar.
                textOverlay - Overlay text is centered within the bar and replaces the underlying bar characters.
                textRight   - Rendered on right side of ProgressBar.

            These sections may be formatted using the following placeholders:

                {VALUE}     - Current progress value.
                {MAX}       - Maximum progress value.
                {PERCENT}   - Progress percentage (0-100).
                {RATIO}     - Progress ratio (0.0-1.0).
                {AVG_ITTS}  - Average iterations per second.
                {AVG_TIME}  - Average time per iteration.
                {ELAPSED}   - Time elapsed since start.
                {REMAINING} - Estimated time remaining.

            Time placeholders ({AVG_TIME}, {ELAPSED}, and {REMAINING}) support
            custom time format specifiers:

                H    - Hours.
                HH   - Zero-padded hours.
                M    - Minutes.
                MM   - Zero-padded minutes.
                S    - Seconds.
                SS   - Zero-padded seconds.
                m    - Tenths.
                mm   - Hundredths.
                mmm  - Milliseconds.

            Default time format is MM:SS.

            Args:
                increment (int):
                    Amount to add to the current progress value.
            """
            with self.mutate:
                # get time diff
                now = time.monotonic()
                dt = now - self.lastUpdateTime
                self.lastUpdateTime = now
                # increment bar value
                self.value = min(self.max, self.value + increment)
                # calc stats
                elapsed = now - self.startTime
                if increment != 0:
                    instant = dt / increment
                else:
                    instant = 0
                if self.averageTime == 0:
                    self.averageTime = instant
                else:
                    self.averageTime = ((1 - self.alpha) * self.averageTime + self.alpha * instant)
                remaining = (self.max - self.value) * self.averageTime
                # get formatted text
                mapping = {
                    "VALUE": self.value,
                    "MAX": self.max,
                    "PERCENT": 100 * self.value / self.max,
                    "RATIO": self.value / self.max,
                    "AVG_TIME": self.averageTime,
                    "AVG_ITTS": 1 / self.averageTime,
                    "ELAPSED": elapsed,
                    "REMAINING": remaining,
                }
                left = self.formatText(self.textLeft, mapping)
                right = self.formatText(self.textRight, mapping)
                overlay = self.formatText(self.textOverlay, mapping)
                # build bar 
                barWidth = max(0, self.displayTile.cols - (len(left) + len(right)))
                barFilled = int(barWidth * self.value / self.max)
                barRaw = (self.barChar * barFilled)[:barFilled] + " " * (barWidth - barFilled)
                midIndex = (len(barRaw) - len(overlay)) // 2
                bar = barRaw[:midIndex] + overlay + barRaw[midIndex + len(overlay):]

                if self.visible:
                    self.displayTile.update((left + bar + right)[:self.displayTile.cols])
                    self.drawText()

        def setColor(self, colors:dict[str, tuple[int, int, int]]=None):
            """
            Sets the colors used to render the tile and border.

            If `colors` is ``None``, all colors are reset to None.

            The `colors` dictionary may contain any combination of the following keys:

                Text:
                    - "TEXT_FG"     : Text foreground color
                    - "TEXT_BG"     : Text background color
                    - "TEXT_FG_F"   : Focused text foreground color
                    - "TEXT_BG_F"   : Focused text background color

                Border:
                    - "BORDER_FG"   : Border foreground color
                    - "BORDER_BG"   : Border background color
                    - "BORDER_FG_F" : Focused border foreground color
                    - "BORDER_BG_F" : Focused border background color

            Each color must be an RGB tuple of the form ``(R, G, B)``, where each
            component is an integer in the range 0-255.

            Args:
                colors: Dictionary mapping color names to RGB tuples. Unspecified
                    colors are left unchanged. If ``None``, all colors are reset.
            """
            with self.mutate:
                self.displayTile.setColor(colors=colors)

    class Alert:
        """
        A terminal UI region that displays a message for a set time.
        """
        def __init__(self, write_func, overlap_func, popup_lock:threading.RLock, exit_event:threading.Event, wait_con:threading.Condition,
            x:int, y:int, width:int, height:int,
            text:str, textWrap:int, textJust:int,
            border:"TerminalTiler.Border",
            colorFG:tuple[int, int, int]=None, colorBG:tuple[int, int, int]=None):
            """
            Initializes an alert dialog.

            Configures the alert geometry, text, colors, and border. The alert is
            rendered as a popup above all other terminal elements.

            Args:
                write_func: Function used to write text to the terminal.
                overlap_func: Function used to determine what tiles the Alert covers.
                popup_lock (threading.RLock): Lock used to ensure only one popup is active at a time.
                exit_event (threading.Event): Event used to signal application shutdown.
                wait_con (threading.Condition): Used to wake sleeping thread.

                x (int): Alert origin column (1-based).
                y (int): Alert origin row (1-based).
                width (int): Alert width in characters.
                height (int): Alert height in rows.

                text (str): Initial alert text.
                textWrap (int): Text wrapping mode. Style.Wrap.WRAP or Style.Wrap.NOWRAP.
                textJust (int): Text justification mode. Style.Justify.LJUST, Style.Justify.CENTERED, or Style.Justify.RJUST.

                border (TerminalTiler.Border): Border configuration.

                colorFG (tuple[int, int, int], optional): Alert foreground RGB color.
                colorBG (tuple[int, int, int], optional): Alert background RGB color.
            """
            self.mutate = threading.RLock()
            self.getOverlaping = overlap_func
            self.lock = popup_lock
            self.exit = exit_event
            self.wait_con = wait_con
            self.close = threading.Event() # user closed alert
            self.close_key = None
            self.text = text
            self.x = x
            self.y = y
            self.width = width
            self.height = height
            self.canFocus = False
            self.visible = False
            self.displayTile = TerminalTiler.DisplayTile(
                write_func=write_func,
                merge_func=None,
                x=x,
                y=y,
                width=width,
                height=height,
                visible=False,
                canFocus=False,
                colorFG=colorFG,
                colorBG=colorBG,
                colorFG_F=colorFG,
                colorBG_F=colorBG,
                textWrap=textWrap,
                textJust=textJust,
                sizeMode=TerminalTiler.Style.Size.FIXED,
                border=border,
                header=TerminalTiler.Header()
            )

        def getRect(self):
            """
            Returns the tile's bounding rectangle.

            Returns:
                tuple[int, int, int, int]: The rectangle as
                ``(x1, y1, x2, y2)``, where:
                    - ``x1`` is the left edge.
                    - ``y1`` is the top edge.
                    - ``x2`` is the right edge (inclusive).
                    - ``y2`` is the bottom edge (inclusive).
            """
            return self.displayTile.getRect()

        def drawBorder(self):
            """
            Render border.
            """
            with self.mutate:
                with self.lock:
                    self.displayTile.drawBorder()

        def drawText(self):
            """
            Render Alert text.
            """
            with self.mutate:
                with self.lock:
                    self.displayTile.text.clear()
                    self.displayTile.update(self.text)

        def handleInput(self, key:str):
            """
            Handles keyboard input to Alert.

            Args:
                key (str): Key pressed.
            """
            if self.close_key and not self.close.is_set() and (key == self.close_key or self.close_key == TerminalTiler.Keyboard.KEY_ANY):
                self.close.set()
                with self.wait_con:
                    self.wait_con.notify_all()

        def show(self, duration: float = 0, close_key: str = None):
            """
            Render the Alert for a specified duration.
            While the alert is visible, other threads are blocked from writing to the terminal.

            Args:
                duration (float):
                    Number of seconds to display the alert.
                    If duration < 0, the alert remains visible until `close_key` is pressed.

                close_key (str):
                    TerminalTiler.Keyboard key that closes the alert.
                    If `duration < 0` and `close_key` is `None`,
                    TerminalTiler.Keyboard.KEY_ANY is used.
            """
            with self.mutate:
                if duration < 0 and close_key is None:
                    close_key = TerminalTiler.Keyboard.KEY_ANY

                with self.lock:
                    self.close_key = close_key
                    self.close.clear()

                    self.visible = True
                    self.displayTile.visible = True
                    self.displayTile.write("\033[?25l".encode())  # hide cursor
                    self.displayTile.drawBorder()
                    self.displayTile.text.clear()
                    self.displayTile.update(self.text)

                    # wait for set time or until keypress
                    while not self.exit.is_set() and not self.close.is_set():
                        with self.wait_con:
                            notified = self.wait_con.wait(None if duration < 0 else duration)

                            if duration >= 0 and not notified:
                                self.close.set()

                    self.hide()
                    self.close_key = None
                    self.close.set()

                    # restore any tiles hidden beneath the alert
                    for tile in self.getOverlaping(self):
                        if tile.visible:
                            tile.show()

        def hide(self):
            """
            Hide element.
            """
            with self.mutate:
                with self.lock:
                    self.visible = False
                    self.displayTile.hide()

        def setColor(self, colors:dict[str, tuple[int, int, int]]=None):
            """
            Sets the colors used to render the tile and border.

            If `colors` is ``None``, all colors are reset to None.

            The `colors` dictionary may contain any combination of the following keys:

                Text:
                    - "TEXT_FG"     : Text foreground color
                    - "TEXT_BG"     : Text background color
                    - "TEXT_FG_F"   : Focused text foreground color
                    - "TEXT_BG_F"   : Focused text background color

                Border:
                    - "BORDER_FG"   : Border foreground color
                    - "BORDER_BG"   : Border background color
                    - "BORDER_FG_F" : Focused border foreground color
                    - "BORDER_BG_F" : Focused border background color

            Each color must be an RGB tuple of the form ``(R, G, B)``, where each
            component is an integer in the range 0-255.

            Args:
                colors: Dictionary mapping color names to RGB tuples. Unspecified
                    colors are left unchanged. If ``None``, all colors are reset.
            """
            with self.mutate:
                self.displayTile.setColor(colors=colors)

    class MessageBox:
        """
        A terminal UI region that displays a message and allows the user to select an option.
        """
        class Button:
            """
            Button
            """
            def __init__(self, write_func,
                value, hotkey:str,
                width:int, height:int,
                text:str, textWrap:int, textJust:int,
                border:"TerminalTiler.Border",
                colorFG:tuple[int, int, int], colorBG:tuple[int, int, int], colorFG_F:tuple[int, int, int], colorBG_F:tuple[int, int, int]):
                """
                Initializes a button.

                Configures the button appearance, text layout, border, colors,
                activation value, and optional keyboard hotkey.

                Args:
                    write_func: Function used to write text to the terminal.

                    value: Value returned when the button is activated.
                    hotkey (str): Keyboard key that activates the button.
                    width (int): Button width in characters.
                    height (int): Button height in rows.

                    text (str): Button label.
                    textWrap (int): Text wrapping mode. Style.Wrap.WRAP or Style.Wrap.NOWRAP.
                    textJust (int): Text justification mode. Style.Justify.LJUST, Style.Justify.CENTERED, or Style.Justify.RJUST.

                    border (TerminalTiler.Border): Border configuration.

                    colorFG (tuple[int, int, int]): Button foreground RGB color.
                    colorBG (tuple[int, int, int]): Button background RGB color.
                    colorFG_F (tuple[int, int, int]): Focused button foreground RGB color.
                    colorBG_F (tuple[int, int, int]): Focused button background RGB color.
                """
                self.mutate = threading.RLock()
                self.write = write_func
                self.text = text
                self.hotkey = hotkey
                self.value = value
                self.width=width
                self.height=height
                self.displayTile = TerminalTiler.DisplayTile(
                    write_func=write_func,
                    merge_func=None,
                    x=0, # set at render
                    y=0, # set at render
                    width=width,
                    height=height,
                    visible=False,
                    canFocus=False,
                    colorFG=colorFG,
                    colorBG=colorBG,
                    colorFG_F=colorFG_F,
                    colorBG_F=colorBG_F,
                    textWrap=textWrap,
                    textJust=textJust,
                    sizeMode=TerminalTiler.Style.Size.FIXED,
                    border=border,
                    header=TerminalTiler.Header()
                )

            def setColor(self, colors:dict[str, tuple[int, int, int]]=None):
                """
                Sets the colors used to render the tile and border.

                If `colors` is ``None``, all colors are reset to None.

                The `colors` dictionary may contain any combination of the following keys:

                    Text:
                        - "TEXT_FG"     : Text foreground color
                        - "TEXT_BG"     : Text background color
                        - "TEXT_FG_F"   : Focused text foreground color
                        - "TEXT_BG_F"   : Focused text background color

                    Border:
                        - "BORDER_FG"   : Border foreground color
                        - "BORDER_BG"   : Border background color
                        - "BORDER_FG_F" : Focused border foreground color
                        - "BORDER_BG_F" : Focused border background color

                Each color must be an RGB tuple of the form ``(R, G, B)``, where each
                component is an integer in the range 0-255.

                Args:
                    colors: Dictionary mapping color names to RGB tuples. Unspecified
                        colors are left unchanged. If ``None``, all colors are reset.
                """
                with self.mutate:
                    self.displayTile.setColor(colors=colors)

        def __init__(self, write_func, overlap_func, popup_lock:threading.RLock, exit_event:threading.Event, wait_con:threading.Condition,
            text:str, headerText:str,
            x:int, y:int, width:int, height:int,
            textWrap:int, textJust:int,
            border:"TerminalTiler.Border",
            header:"TerminalTiler.Header",
            colorFG:tuple[int, int, int], colorBG:tuple[int, int, int]):
            """
            Initializes a message box.

            Configures the message box geometry, body text, header, colors, and
            border. The message box is rendered as a popup above all other
            terminal elements.

            Args:
                write_func: Function used to write text to the terminal.
                overlap_func: Function used to determine what tiles the Button covers.
                popup_lock (threading.RLock): Lock used to ensure only one popup is active at a time.
                exit_event (threading.Event): Event used to signal application shutdown.
                wait_con (threading.Condition): Used to wake sleeping thread.

                text (str): Initial message box text.
                headerText (str): Header text displayed at the top of the message box.

                x (int): Message box origin column (1-based).
                y (int): Message box origin row (1-based).
                width (int): Message box width in characters.
                height (int): Message box height in rows.

                textWrap (int): Text wrapping mode. Style.Wrap.WRAP or Style.Wrap.NOWRAP.
                textJust (int): Text justification mode. Style.Justify.LJUST, Style.Justify.CENTERED, or Style.Justify.RJUST.

                border (TerminalTiler.Border): Border configuration.
                header (TerminalTiler.Header): Header configuration.

                colorFG (tuple[int, int, int]): Message box foreground RGB color.
                colorBG (tuple[int, int, int]): Message box background RGB color.
            """
            self.mutate = threading.RLock()
            self.write = write_func
            self.getOverlaping = overlap_func
            self.lock = popup_lock
            self.exit = exit_event
            self.wait_con = wait_con
            self.close = threading.Event() # user closed message
            self.input = threading.Event() # user input
            self.text = text
            self.headerText = headerText
            self.x = x
            self.y = y
            self.width = width
            self.height = height
            self.canFocus = False
            self.visible = False
            self.waitTime = 0.1
            self.buttons = []
            self.focusedIndex = -1 # focused button index
            self.value = None
            self.displayTile = TerminalTiler.DisplayTile(
                write_func=write_func,
                merge_func=None,
                x=x,
                y=y,
                width=width,
                height=height,
                visible=False,
                canFocus=False,
                colorFG=colorFG,
                colorBG=colorBG,
                colorFG_F=colorFG,
                colorBG_F=colorBG,
                textWrap=textWrap,
                textJust=textJust,
                sizeMode=TerminalTiler.Style.Size.FIXED,
                border=border,
                header=header
            )

        def getRect(self):
            """
            Returns the tile's bounding rectangle.

            Returns:
                tuple[int, int, int, int]: The rectangle as
                ``(x1, y1, x2, y2)``, where:
                    - ``x1`` is the left edge.
                    - ``y1`` is the top edge.
                    - ``x2`` is the right edge (inclusive).
                    - ``y2`` is the bottom edge (inclusive).
            """
            return self.displayTile.getRect()

        def getButtonLayoutHeight(self)->int:
            """
            Calculate the minimum height required to display buttons in centered
            rows with equal horizontal spacing.

            Each row has:
                - at least 1 column between adjacent rectangles
                - at least 1 column between the left/right edges and the rectangles

            Returns:
                int: Total layout height.
            """
            with self.mutate:
                total_height = 0
                row_width = 0
                row_height = 0
                row_count = 0
                rows = 0

                for b in self.buttons:
                    candidate_width = row_width + b.width
                    candidate_count = row_count + 1

                    # need candidate_count + 1 gaps (left, right, between)
                    if candidate_width + candidate_count + 1 <= self.displayTile.cols:
                        row_width = candidate_width
                        row_height = max(row_height, b.height)
                        row_count = candidate_count
                    else:
                        total_height += row_height
                        rows += 1

                        row_width = b.width
                        row_height = b.height
                        row_count = 1

                if row_count:
                    total_height += row_height
                    rows += 1

                if rows > 1:
                    total_height += (rows - 1)

                return total_height + 2

        def addButton(self,
            value,
            width:int, height:int,
            text:str, textWrap:int=None, textJust:int=None,
            colorFG:tuple[int, int, int]=None, colorBG:tuple[int, int, int]=None, colorFG_F:tuple[int, int, int]=None, colorBG_F:tuple[int, int, int]=None,
            borderStyle:int=None, borderChar:str=None, borderStyleFocused:int=None, borderCharFocused:str=None,
            borderFG:tuple[int, int, int]=None, borderBG:tuple[int, int, int]=None, borderFG_F:tuple[int, int, int]=None, borderBG_F:tuple[int, int, int]=None,
            hotkey:str=None)->Button:
            """
            Creates and registers a new Button.

            Initializes a button with the specified text, colors, border, and
            optional keyboard hotkey before adding it to the message box.

            Args:
                value: Value returned when the button is activated.
                width (int): Button width in characters.
                height (int): Button height in rows.

                text (str): Button label.
                textWrap (int, optional): Text wrapping mode. Style.Wrap.WRAP or Style.Wrap.NOWRAP.
                textJust (int, optional): Text justification mode. Style.Justify.LJUST, Style.Justify.CENTERED, or Style.Justify.RJUST.

                colorFG (tuple[int, int, int], optional): Button foreground RGB color.
                colorBG (tuple[int, int, int], optional): Button background RGB color.
                colorFG_F (tuple[int, int, int], optional): Focused button foreground RGB color. Defaults to `colorFG`.
                colorBG_F (tuple[int, int, int], optional): Focused button background RGB color. Defaults to `colorBG`.

                borderStyle (int, optional): Border style constant.
                borderChar (str, optional): Custom border character set. Overrides `borderStyle`.
                borderStyleFocused (int, optional): Border style used while focused. Defaults to `borderStyle`.
                borderCharFocused (str, optional): Custom focused border character set. Overrides `borderStyleFocused`. Defaults to `borderChar`.

                borderFG (tuple[int, int, int], optional): Border foreground RGB color.
                borderBG (tuple[int, int, int], optional): Border background RGB color.
                borderFG_F (tuple[int, int, int], optional): Focused border foreground RGB color. Defaults to `borderFG`.
                borderBG_F (tuple[int, int, int], optional): Focused border background RGB color. Defaults to `borderBG`.

                hotkey (str, optional): Keyboard key that activates the button.

            Returns:
                Button: The newly created Button instance.
            """
            with self.mutate:
                if width > self.displayTile.cols - 2:
                    raise ValueError(f"Button width exceeds MessageBox available space. ({width} > {self.displayTile.cols - 2})")
                elif height > self.displayTile.rows - 2:
                    raise ValueError(f"Button height exceeds MessageBox available space. ({height} > {self.displayTile.rows - 2})")
                button = self.Button(
                    write_func=self.write,
                    value=value,
                    width=width,
                    height=height,
                    text=text,
                    textWrap=textWrap,
                    textJust=textJust,
                    colorFG=colorFG,
                    colorBG=colorBG,
                    colorFG_F=colorFG_F,
                    colorBG_F=colorBG_F,
                    border=TerminalTiler.Border(
                        style=borderStyle,
                        charset=borderChar,
                        colorFG=borderFG,
                        colorBG=borderBG,
                        style_F=borderStyleFocused,
                        charset_F=borderCharFocused,
                        colorFG_F=borderFG_F,
                        colorBG_F=borderBG_F
                    ),
                    hotkey=hotkey
                )
                self.buttons.append(button)
                if self.getButtonLayoutHeight() > self.displayTile.rows:
                    raise ValueError("Unable to fit all Buttons in MessageBox available space.")
                return button

        def drawBorder(self):
            """
            Render border.
            """
            with self.mutate:
                with self.lock:
                    self.displayTile.drawBorder()

        def drawText(self):
            """
            Render MessageBox text.
            """
            with self.mutate:
                with self.lock:
                    button_rows = self.getButtonLayoutHeight()
                    self.displayTile.text.clear()
                    self.displayTile.update(self.text + '\n ' * button_rows)

        def drawButtons(self):
            with self.mutate:
                rows = []
                row = []
                row_width = 0
                row_height = 0
                total_height = 0

                # build rows
                for b in self.buttons:
                    candidate_width = row_width + b.width
                    candidate_count = len(row) + 1

                    if candidate_width + candidate_count + 1 <= self.displayTile.cols:
                        row.append(b)
                        row_width = candidate_width
                        row_height = max(row_height, b.height)
                    else:
                        rows.append((row, row_width, row_height))
                        total_height += row_height

                        row = [b]
                        row_width = b.width
                        row_height = b.height

                if row:
                    rows.append((row, row_width, row_height))
                    total_height += row_height

                total_height += len(rows) + 1

                # draw buttons
                y = 0
                for row, row_width, row_height in rows:
                    # distribute empty space
                    total_space = self.displayTile.cols - row_width
                    gap_count = len(row) + 1
                    base = total_space // gap_count
                    extra = total_space % gap_count

                    gaps = [base] * gap_count
                    order = []
                    left = (gap_count - 1) // 2
                    right = gap_count // 2

                    while left >= 0 or right < gap_count:
                        if left >= 0:
                            order.append(left)
                            left -= 1
                        if right < gap_count:
                            order.append(right)
                            right += 1

                    for i in range(extra):
                        gaps[order[i]] += 1

                    # set button position and call drawing method
                    x = gaps[0]
                    for i, b in enumerate(row):
                        b.displayTile.x = x + self.displayTile.tx
                        b.displayTile.y = y + self.displayTile.ty + (self.displayTile.rows - (total_height)) + 1
                        b.displayTile.resize(width=b.width, height=b.height)
                        b.displayTile.drawBorder()
                        b.displayTile.text.clear()
                        b.displayTile.update(b.text)
                        b.displayTile.drawText()

                        x += b.displayTile.width + gaps[i + 1]

                    y += row_height + 1

        def handleInput(self, key:str):
            """
            Handles keyboard input to MessageBox.

            Args:
                key (str): Key pressed.
            """
            # handle tab
            if key == TerminalTiler.Keyboard.KEY_TAB:
                # clear old focus
                if 0 <= self.focusedIndex and self.focusedIndex < len(self.buttons):
                    self.buttons[self.focusedIndex].displayTile.focused = False

                # move forward
                self.focusedIndex += 1

                # apply or reset
                if self.focusedIndex < len(self.buttons):
                    self.buttons[self.focusedIndex].displayTile.focused = True
                else:
                    self.focusedIndex = -1
                
                self.input.set()
                with self.wait_con:
                    self.wait_con.notify_all()

            elif key == TerminalTiler.Keyboard.KEY_ENTER:
                if self.focusedIndex >= 0:
                    self.value = self.buttons[self.focusedIndex].value
                    self.close.set()
                    with self.wait_con:
                        self.wait_con.notify_all()

            else:
                for button in self.buttons:
                    if key == button.hotkey:
                        self.value = button.value
                        self.close.set()
                        with self.wait_con:
                            self.wait_con.notify_all()
                        break

        def show(self):
            """
            Render the MessageBox.
            While the MessageBox is visible, other threads are blocked from writing to the terminal.

            Returns:
                Button.value from selected Button.
            """
            with self.mutate:
                if len(self.buttons) > 0:
                    with self.lock:
                        self.buttons[self.focusedIndex].displayTile.focused = False
                        self.focusedIndex = -1
                        self.value = None
                        self.close.clear()
                        self.visible = True
                        self.displayTile.visible = True
                        self.displayTile.write("\033[?25l".encode())  # hide cursor
                        self.displayTile.drawBorder()
                        if self.displayTile.header:
                            self.displayTile.header.text.clear()
                            self.displayTile.updateHeader(self.headerText)
                        self.drawText()
                        self.drawButtons()

                        # wait for button press
                        while not self.exit.is_set() and not self.close.is_set():
                            with self.wait_con:
                                while (not self.input.is_set() and not self.exit.is_set() and not self.close.is_set()):
                                    self.wait_con.wait()

                                if self.exit.is_set() or self.close.is_set():
                                    break

                                self.input.clear()

                            self.drawButtons()

                        self.hide()
                        # restore any tiles hidden beneath the alert
                        for tile in self.getOverlaping(self):
                            if tile.visible:
                                tile.show()
                    return self.value

        def hide(self):
            """
            Hide element.
            """
            with self.mutate:
                with self.lock:
                    self.visible = False
                    self.displayTile.hide()

        def setColor(self, colors:dict[str, tuple[int, int, int]]=None):
            """
            Sets the colors used to render the tile, border and buttons.

            If `colors` is ``None``, all colors are reset to None.

            The `colors` dictionary may contain any combination of the following keys:

                Text:
                    - "TEXT_FG"     : Text foreground color
                    - "TEXT_BG"     : Text background color
                    - "TEXT_FG_F"   : Focused text foreground color
                    - "TEXT_BG_F"   : Focused text background color

                Border:
                    - "BORDER_FG"   : Border foreground color
                    - "BORDER_BG"   : Border background color
                    - "BORDER_FG_F" : Focused border foreground color
                    - "BORDER_BG_F" : Focused border background color

                Button Text:
                    - "BUTTON_TEXT_FG"     : Button text foreground color
                    - "BUTTON_TEXT_BG"     : Button text background color
                    - "BUTTON_TEXT_FG_F"   : Focused button text foreground color
                    - "BUTTON_TEXT_BG_F"   : Focused text button background color

                Button Border:
                    - "BUTTON_BORDER_FG"   : Button border foreground color
                    - "BUTTON_BORDER_BG"   : Button border background color
                    - "BUTTON_BORDER_FG_F" : Focused button border foreground color
                    - "BUTTON_BORDER_BG_F" : Focused button border background color

            Each color must be an RGB tuple of the form ``(R, G, B)``, where each
            component is an integer in the range 0-255.

            Args:
                colors: Dictionary mapping color names to RGB tuples. Unspecified
                    colors are left unchanged. If ``None``, all colors are reset.
            """
            with self.mutate:
                self.displayTile.setColor(colors=colors)

                if colors is None:
                    for b in self.buttons:
                        b.setColor(colors=colors)
                else:
                    bColors = {k.removeprefix("BUTTON_"): v for k, v in colors.items() if k.startswith("BUTTON_")}
                    for b in self.buttons:
                        b.setColor(colors=bColors)

                if self.visible:
                    self.show()

    class Table:
        """
        A terminal UI region that displays a table.
        """
        class Cell:
            """
            Stores text and formatting info for a Table cell.
            """
            def __init__(self, write_func,
                text:str, textWrap:int, textJust:int,
                colorFG:tuple[int, int, int], colorBG:tuple[int, int, int], colorFG_F:tuple[int, int, int], colorBG_F:tuple[int, int, int]):
                """
                Initializes a table cell.

                Configures the cell text, layout, and colors used when the cell
                is rendered.

                Args:
                    write_func: Function used to write text to the terminal.
                    text (str): Initial cell text.
                    textWrap (int): Text wrapping mode. Style.Wrap.WRAP or Style.Wrap.NOWRAP.
                    textJust (int): Text justification mode. Style.Justify.LJUST, Style.Justify.CENTERED, or Style.Justify.RJUST.

                    colorFG (tuple[int, int, int]): Cell foreground RGB color.
                    colorBG (tuple[int, int, int]): Cell background RGB color.
                    colorFG_F (tuple[int, int, int]): Focused cell foreground RGB color.
                    colorBG_F (tuple[int, int, int]): Focused cell background RGB color.
                """
                self.mutate = threading.RLock()
                self.text = text
                self.textWrap = textWrap
                self.textJust = textJust
                self.displayTile = TerminalTiler.DisplayTile(
                    write_func=write_func,
                    merge_func=None,
                    x=0,
                    y=0,
                    width=0,
                    height=0,
                    visible=False,
                    canFocus=False,
                    textWrap=textWrap,
                    textJust=textJust,
                    colorFG=colorFG,
                    colorBG=colorBG,
                    colorFG_F=colorFG_F,
                    colorBG_F=colorBG_F,
                    sizeMode=TerminalTiler.Style.Size.FIXED,
                    border=TerminalTiler.Border(),
                    header=TerminalTiler.Header()
                )

            def update(self, text:str):
                """
                Update the cell's displayed text.
                Current text is cleared. New text is rendered.

                Args:
                    text (str):
                        The new text to display in the cell.
                """
                with self.mutate:
                    self.text = text
                    self.displayTile.text.clear()
                    self.displayTile.update(text)

            def setColor(self, colors:dict[str, tuple[int, int, int]]=None):
                """
                Sets the colors used to render the text.

                If `colors` is ``None``, all colors are reset to None.

                The `colors` dictionary may contain any combination of the following keys:

                    Text:
                        - "TEXT_FG"     : Text foreground color
                        - "TEXT_BG"     : Text background color
                        - "TEXT_FG_F"   : Focused text foreground color
                        - "TEXT_BG_F"   : Focused text background color

                Each color must be an RGB tuple of the form ``(R, G, B)``, where each
                component is an integer in the range 0-255.

                Args:
                    colors: Dictionary mapping color names to RGB tuples. Unspecified
                        colors are left unchanged. If ``None``, all colors are reset.
                """
                with self.mutate:
                    self.displayTile.setColor(colors=colors)

            def setTextWrap(self, textWrap:int=None):
                """
                Sets the cell's text wrapping mode.

                If `textWrap` is invalid or ``None``, the wrapping mode defaults
                to `Style.Wrap.NOWRAP`.

                Args:
                    textWrap (int, optional): Text wrapping mode. Style.Wrap.WRAP or Style.Wrap.NOWRAP.
                """
                with self.mutate:
                    self.textWrap = textWrap if textWrap in TerminalTiler.Style.Wrap.STYLES else TerminalTiler.Style.Wrap.NOWRAP
                    self.displayTile.textWrap = self.textWrap

            def setTextJust(self, textJust:int=None):
                """
                Sets the cell's text justification mode.

                If `textJust` is invalid or ``None``, the justification defaults
                to `Style.Justify.LJUST`.

                Args:
                    textJust (int, optional): Text justification mode. Style.Justify.LJUST, Style.Justify.CENTERED, or Style.Justify.RJUST.
                """
                with self.mutate:
                    self.textJust = textJust if textJust in TerminalTiler.Style.Justify.STYLES else TerminalTiler.Style.Justify.LJUST
                    self.displayTile.textJust = self.textJust

        class Axis:
            """
            Represents a table axis (row or column).

            An Axis stores a collection of cells and the size assigned to that
            row or column during layout.
            """
            def __init__(self, cells:list, size:int):
                """
                Initializes a table axis.

                Args:
                    cells (list): Cells contained in the row or column.
                    size (int): Width (for columns) or height (for rows) in characters.
                """
                self.mutate = threading.RLock()
                self.cells = cells
                self.size = size # width/height of row/col

            def setColor(self, colors:dict[str, tuple[int, int, int]]=None):
                """
                Sets the colors used to render the text.

                If `colors` is ``None``, all colors are reset to None.

                The `colors` dictionary may contain any combination of the following keys:

                    Text:
                        - "TEXT_FG"     : Text foreground color
                        - "TEXT_BG"     : Text background color
                        - "TEXT_FG_F"   : Focused text foreground color
                        - "TEXT_BG_F"   : Focused text background color

                Each color must be an RGB tuple of the form ``(R, G, B)``, where each
                component is an integer in the range 0-255.

                Args:
                    colors: Dictionary mapping color names to RGB tuples. Unspecified
                        colors are left unchanged. If ``None``, all colors are reset.
                """
                with self.mutate:
                    for c in self.cells:
                        c.setColor(colors=colors)

            def setTextWrap(self, textWrap:int=None):
                """
                Sets the text wrapping mode for every cell in the axis.

                If `textWrap` is invalid or ``None``, each cell uses Style.Wrap.NOWRAP.

                Args:
                    textWrap (int, optional): Text wrapping mode. Style.Wrap.WRAP or Style.Wrap.NOWRAP.
                """
                with self.mutate:
                    for c in self.cells:
                        c.setTextWrap(textWrap)

            def setTextJust(self, textJust:int=None):
                """
                Sets the text justification mode for every cell in the axis.

                If `textJust` is invalid or ``None``, each cell uses Style.Justify.LJUST.

                Args:
                    textJust (int, optional): Text justification mode. Style.Justify.LJUST, Style.Justify.CENTERED, or Style.Justify.RJUST.
                """
                with self.mutate:
                    for c in self.cells:
                        c.setTextJust(textJust)

        def __init__(self, write_func, merge_func,
            x:int, y:int, width:int, height:int,
            visible:bool, canFocus:bool,
            textWrap: int, textJust: int,
            border:"TerminalTiler.Border",
            header:"TerminalTiler.Header",
            colorFG:tuple[int, int, int], colorBG:tuple[int, int, int], colorFG_F:tuple[int, int, int], colorBG_F:tuple[int, int, int]):
            """
            Initializes a table.

            Configures the table geometry, visibility, text layout, colors, border,
            and optional header. The table manages a grid of cells that can be
            individually updated while sharing common rendering settings.

            Args:
                write_func: Function used to write text to the terminal.
                merge_func: Function used to merge borders.
                x (int): Table origin column (1-based).
                y (int): Table origin row (1-based).
                width (int): Table width in characters.
                height (int): Table height in rows.
                visible (bool): Whether the table is initially visible.
                canFocus (bool): Whether the table can receive keyboard focus.

                textWrap (int): Default text wrapping mode for table cells. Style.Wrap.WRAP or Style.Wrap.NOWRAP.
                textJust (int): Default text justification mode for table cells. Style.Justify.LJUST, Style.Justify.CENTERED, or Style.Justify.RJUST.

                border (TerminalTiler.Border): Border configuration.
                header (TerminalTiler.Header): Header configuration.

                colorFG (tuple[int, int, int]): Default cell foreground RGB color.
                colorBG (tuple[int, int, int]): Default cell background RGB color.
                colorFG_F (tuple[int, int, int]): Default focused cell foreground RGB color.
                colorBG_F (tuple[int, int, int]): Default focused cell background RGB color.
            """
            self.mutate = threading.RLock()
            self.table_rows = 0
            self.table_cols = 0
            self.row_list = []
            self.col_list = []
            self.textWrap = textWrap if textWrap in TerminalTiler.Style.Wrap.STYLES else TerminalTiler.Style.Wrap.NOWRAP # default textWrap for cells
            self.textJust = textJust if textJust in TerminalTiler.Style.Justify.STYLES else TerminalTiler.Style.Justify.LJUST # default textJust for cells
            self.write = write_func
            self.x = x
            self.y = y
            self.width = width
            self.height = height
            self.visible = visible
            self.focused = False
            self.displayTile = TerminalTiler.DisplayTile(
                write_func=write_func,
                merge_func=merge_func,
                x=x,
                y=y,
                width=width,
                height=height,
                visible=False,
                canFocus=canFocus,
                colorFG=None,
                colorBG=None,
                colorFG_F=None,
                colorBG_F=None,
                textWrap=TerminalTiler.Style.Wrap.NOWRAP,
                textJust=TerminalTiler.Style.Justify.LJUST,
                sizeMode=TerminalTiler.Style.Size.FIXED,
                border=border,
                header=header
            )

            # colors
            self.colorFG = colorFG
            self.colorBG = colorBG
            self.colorFG_F = colorFG_F
            self.colorBG_F = colorBG_F

        def getRect(self):
            """
            Returns the tile's bounding rectangle.

            Returns:
                tuple[int, int, int, int]: The rectangle as
                ``(x1, y1, x2, y2)``, where:
                    - ``x1`` is the left edge.
                    - ``y1`` is the top edge.
                    - ``x2`` is the right edge (inclusive).
                    - ``y2`` is the bottom edge (inclusive).
            """
            return self.displayTile.getRect()

        def build(self):
            """
            Builds the table layout.

            Creates the table cell grid and initializes the row and column axis collections.
            The available display area is divided evenly among all rows and columns.

            Existing cells and axis objects are replaced.
            """
            with self.mutate:
                col_base = (self.displayTile.cols - (self.table_cols - 1)) // self.table_cols
                col_extra = (self.displayTile.cols - (self.table_cols - 1)) % self.table_cols

                row_base = (self.displayTile.rows - (self.table_rows - 1)) // self.table_rows
                row_extra = (self.displayTile.rows - (self.table_rows - 1)) % self.table_rows

                # create the cell grid
                self.cells = [
                    [
                        self.Cell(
                            self.write,
                            text="",
                            textWrap=self.textWrap,
                            textJust=self.textJust,
                            colorFG=self.colorFG,
                            colorBG=self.colorBG,
                            colorFG_F=self.colorFG_F,
                            colorBG_F=self.colorBG_F
                        ) for _ in range(self.table_cols)
                    ] for _ in range(self.table_rows)
                ]

                # create row axis list
                self.row_list = [
                    self.Axis(
                        self.cells[r],
                        row_base + (1 if r < row_extra else 0)
                    ) for r in range(self.table_rows)
                ]

                # create column axis list
                self.col_list = [
                    self.Axis(
                        [self.cells[r][c] for r in range(self.table_rows)],
                        col_base + (1 if c < col_extra else 0)
                    ) for c in range(self.table_cols)
                ]

        def load(self, data:list[list]):
            """
            Loads tabular data into the table.

            The table is resized to match the dimensions of `data`, rebuilding
            its internal cell grid as needed. Each value is converted to a
            string and assigned to the corresponding cell.

            Rows may have different lengths. Any cells beyond the end of a
            shorter row remain empty.

            Args:
                data (list[list]): Two-dimensional sequence of values to load
                    into the table.
            """
            with self.mutate:
                self.table_cols = max([len(r) for r in data])
                self.table_rows = len(data)
                self.build()

                for r in range(self.table_rows):
                    for c in range(len(data[r])):
                        self.cells[r][c].text = str(data[r][c])

        def insertRow(self, data: list, index: int = None):
            """
            Inserts a row into the table.

            The new row uses the table's default cell formatting. If `index` is
            ``None``, the row is appended to the end of the table.

            Args:
                data (list): Values for the new row.
                index (int, optional): Zero-based insertion index.
            """
            with self.mutate:
                if index is None:
                    index = self.table_rows
                else:
                    index = max(0, min(index, self.table_rows))

                row = [
                    self.Cell(
                        self.write,
                        text=str(data[c]) if c < len(data) else "",
                        textWrap=self.textWrap,
                        textJust=self.textJust,
                        colorFG=self.colorFG,
                        colorBG=self.colorBG,
                        colorFG_F=self.colorFG_F,
                        colorBG_F=self.colorBG_F
                    )
                    for c in range(max(self.table_cols, len(data)))
                ]

                self.cells.insert(index, row)

                self.table_rows += 1
                self.table_cols = max(self.table_cols, len(row))

                self.row_list.insert(
                    index,
                    self.Axis(row, 0)
                )

                row_base = (self.displayTile.rows - (self.table_rows - 1)) // self.table_rows
                row_extra = (self.displayTile.rows - (self.table_rows - 1)) % self.table_rows

                self.row_list = [
                    self.Axis(
                        self.cells[r],
                        row_base + (1 if r < row_extra else 0)
                    )
                    for r in range(self.table_rows)
                ]

                # rebuild column axes because column cell references changed
                self.col_list = [
                    self.Axis(
                        [self.cells[r][c] for r in range(self.table_rows)],
                        self.col_list[c].size if c < len(self.col_list) else 0
                    )
                    for c in range(self.table_cols)
                ]

                if self.visible:
                    self.show()

        def insertCol(self, data: list, index: int = None):
            """
            Inserts a column into the table.

            The new column uses the table's default cell formatting. If `index`
            is ``None``, the column is appended to the end of the table.

            Args:
                data (list): Values for the new column.
                index (int, optional): Zero-based insertion index.
            """
            with self.mutate:
                if index is None:
                    index = self.table_cols
                else:
                    index = max(0, min(index, self.table_cols))

                # add cells to each row
                for r in range(self.table_rows):
                    self.cells[r].insert(
                        index,
                        self.Cell(
                            self.write,
                            text=str(data[r]) if r < len(data) else "",
                            textWrap=self.textWrap,
                            textJust=self.textJust,
                            colorFG=self.colorFG,
                            colorBG=self.colorBG,
                            colorFG_F=self.colorFG_F,
                            colorBG_F=self.colorBG_F
                        )
                    )

                # handle empty table / extra data rows
                while self.table_rows < len(data):
                    self.cells.append([
                        self.Cell(
                            self.write,
                            text="",
                            textWrap=self.textWrap,
                            textJust=self.textJust,
                            colorFG=self.colorFG,
                            colorBG=self.colorBG,
                            colorFG_F=self.colorFG_F,
                            colorBG_F=self.colorBG_F
                        )
                        for _ in range(self.table_cols)
                    ])

                    self.table_rows += 1

                    self.cells[-1][index].text = str(data[self.table_rows - 1])

                self.table_cols += 1

                col_base = (self.displayTile.cols - (self.table_cols - 1)) // self.table_cols
                col_extra = (self.displayTile.cols - (self.table_cols - 1)) % self.table_cols

                self.col_list = [
                    self.Axis(
                        [self.cells[r][c] for r in range(self.table_rows)],
                        col_base + (1 if c < col_extra else 0)
                    )
                    for c in range(self.table_cols)
                ]

                if self.visible:
                    self.show()

        def update(self, x:int, y:int, text:str):
            """
            Updates the text of a single table cell.

            Args:
                x (int): Zero-based column index of the cell.
                y (int): Zero-based row index of the cell.
                text (str): New text to display in the cell.
            """
            with self.mutate:
                self.cells[y][x].update(text)

        def updateHeader(self, text:str):
            """
            Appends new text to the tile's header buffer and renders
            the visible header region in the terminal.

            Args:
                text (str): Text to add to text buffer.
            """
            self.displayTile.updateHeader(text)

        def drawBorder(self):
            """
            Draws the table border and internal grid lines.
            """
            with self.mutate:
                if self.displayTile.border.style != TerminalTiler.Border.NO_BORDER:
                    self.displayTile.drawBorder()

                    # draw table lines and juncts
                    if self.focused:
                        color_fg = self.displayTile.border.colorFG_F
                        color_bg = self.displayTile.border.colorBG_F
                    else:
                        color_fg = self.displayTile.border.colorFG
                        color_bg = self.displayTile.border.colorBG

                    visible_cols = [c for c in self.col_list if c.size > 0]
                    visible_rows = [r for r in self.row_list if r.size > 0]

                    # row borders
                    top_border = (
                        (self.displayTile.border.charset.junctionVE if self.displayTile.header.rows > 0 else self.displayTile.border.charset.cornerNW) +
                        self.displayTile.border.charset.junctionHS.join(self.displayTile.border.charset.lineH * c.size for c in visible_cols) +
                        (self.displayTile.border.charset.junctionVW if self.displayTile.header.rows > 0 else self.displayTile.border.charset.cornerNE)
                    )
                    middle_border = (
                        self.displayTile.border.charset.junctionVE +
                        self.displayTile.border.charset.junctionAll.join(self.displayTile.border.charset.lineH * c.size for c in visible_cols) +
                        self.displayTile.border.charset.junctionVW
                    )
                    bottom_border = (
                        self.displayTile.border.charset.cornerSW +
                        self.displayTile.border.charset.junctionHN.join(self.displayTile.border.charset.lineH * c.size for c in visible_cols) +
                        self.displayTile.border.charset.cornerSE
                    )
                    self.write(f"\x1b[{self.displayTile.ty - 1};{self.displayTile.x}H{top_border}".encode(), color_fg, color_bg)
                    self.write(f"\x1b[{self.displayTile.ty + self.displayTile.rows};{self.displayTile.x}H{bottom_border}".encode(), color_fg, color_bg)

                    # col borders
                    y = self.displayTile.ty
                    for i, r in enumerate(visible_rows):
                        x = self.displayTile.tx
                        height = r.size
                        for c in visible_cols:
                            width = c.size
                            x += width + 1
                            for offset in range(height):
                                self.write(f"\x1b[{y + offset};{x - 1}H{self.displayTile.border.charset.lineV}".encode(), color_fg, color_bg)

                        y += height + 1
                        if i < len(visible_rows) - 1:
                            self.write(f"\x1b[{y - 1};{self.displayTile.x}H{middle_border}".encode(), color_fg, color_bg)

                    self.displayTile.mergeBorder(self)

        def show(self):
            """
            Renders the table.

            Row heights and column widths are clamped to the available display area,
            with the final row and column expanded as needed to consume any
            remaining space. Any cells outside the visible area are not shown.
            """
            with self.mutate:
                self.displayTile.drawHeader()

                parent_x2 = self.displayTile.tx + self.displayTile.cols
                parent_y2 = self.displayTile.ty + self.displayTile.rows

                y = self.displayTile.ty
                for r in range(self.table_rows):
                    x = self.displayTile.tx

                    # requested row height
                    height = self.row_list[r].size

                    # clamp if this row would overflow
                    if y + height > parent_y2:
                        height = max(0, parent_y2 - y)

                    # last row grows to fill any remaining space
                    if (r == self.table_rows - 1):
                        height = max(height, parent_y2 - y)

                    # bottom border of last row is at bottom of display
                    if r < self.table_rows - 1 and y + height + 1 == parent_y2:
                        height += 1

                    # update row size
                    self.row_list[r].size = height

                    for c in range(self.table_cols):
                        # Requested column width
                        width = self.col_list[c].size

                        # clamp if this column would overflow
                        if x + width > parent_x2:
                            width = max(0, parent_x2 - x)

                        # last column grows to fill any remaining space
                        if c == self.table_cols - 1:
                            width = max(width, parent_x2 - x)

                        # right border of last col is at right of display
                        if r < self.table_cols - 1 and x + width + 1 == parent_x2:
                            width += 1

                        # update col size
                        self.col_list[c].size = width

                        cell = self.cells[r][c]
                        cell.displayTile.x = x
                        cell.displayTile.y = y
                        cell.displayTile.width = width
                        cell.displayTile.height = height
                        cell.displayTile.resize()
                        cell.displayTile.focused = self.focused
                        cell.displayTile.text.clear()
                        cell.displayTile.visible = True
                        cell.displayTile.update(cell.text)

                        x += width + 1

                    y += height + 1

                self.drawBorder()

        def hide(self):
            """
            Hides table.
            """
            with self.mutate:
                self.visible = False
                self.displayTile.hide()

        def escapeCSV(self, text)->str:
            """
            Escapes text according to CSV format.

            Args:
                text (str): Text to escape.

            Returns:
                str: Escaped text.
            """
            if any(c in text for c in [',', '\n', '\r', '"']):
                return '"' + text.replace('"', '""') + '"'
            return text

        def dump(self)->str:
            """
            Dump contents of Table as CSV.

            Returns:
                str: Table contents in CSV format.
            """
            with self.mutate:
                return '\n'.join(','.join(self.escapeCSV(cell.text) for cell in row.cells) for row in self.row_list)

        def setColor(self, colors:dict[str, tuple[int, int, int]]=None):
            """
            Sets the colors used to render the tile, border, and header.

            If `colors` is ``None``, all colors are reset to None.

            The `colors` dictionary may contain any combination of the following keys:

                Text:
                    - "TEXT_FG"     : Text foreground color
                    - "TEXT_BG"     : Text background color
                    - "TEXT_FG_F"   : Focused text foreground color
                    - "TEXT_BG_F"   : Focused text background color

                Border:
                    - "BORDER_FG"   : Border foreground color
                    - "BORDER_BG"   : Border background color
                    - "BORDER_FG_F" : Focused border foreground color
                    - "BORDER_BG_F" : Focused border background color

                Header:
                    - "HEADER_FG"   : Header foreground color
                    - "HEADER_BG"   : Header background color
                    - "HEADER_FG_F" : Focused header foreground color
                    - "HEADER_BG_F" : Focused header background color

            Each color must be an RGB tuple of the form ``(R, G, B)``, where each
            component is an integer in the range 0-255.

            Args:
                colors: Dictionary mapping color names to RGB tuples. Unspecified
                    colors are left unchanged. If ``None``, all colors are reset.
            """
            with self.mutate:
                if colors is None:
                    self.colorFG = None
                    self.colorBG = None
                    self.colorFG_F = None
                    self.colorBG_F = None

                else:
                    for k, v in colors.items():
                        if k == "TEXT_FG":
                            self.colorFG = v
                        elif k == "TEXT_BG":
                            self.colorBG = v
                        elif k == "TEXT_FG_F":
                            self.colorFG_F = v
                        elif k == "TEXT_BG_F":
                            self.colorBG_F = v

                self.displayTile.setColor(colors=colors)

                for _ in self.cells:
                    for c in _:
                        c.setColor(colors=colors)

                if self.visible:
                    self.show()

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
        self.lock = threading.Lock() # write lock
        self.popup = threading.RLock() # popup lock
        self.exit = threading.Event()
        self.cols, self.rows = os.get_terminal_size()
        self.focusedIndex = -1 # index of active element
        self.tiles = [] # holds all tile elements
        self.wait_con = threading.Condition() # used to wake waiting threads
        self.waitKey = None # used by waitForKey
        self.stdout_FDI = TerminalTiler.FDInterceptor(1, self.exit, self.wait_con)
        self.keyboard = TerminalTiler.Keyboard()
        self.keyboard.subscribe(self._handleInput)
        self.keyboard.start(self.exit)
        self._write("\033[?25l".encode()) # hide cursor
        self.clearScreen()

    def isAlive(self)->bool:
        """
        Checks whether the TerminalTiler is still running.

        Returns:
            bool: True if the shutdown event has not been set, otherwise False.
        """
        return not self.exit.is_set()

    def addDisplayTile(self,
        x:int, y:int, width:int, height:int,
        visible:bool=True, canFocus:bool=True,
        textWrap:int=None, textJust:int=None, sizeMode:int=None,
        colorFG:tuple[int, int, int]=None, colorBG:tuple[int, int, int]=None, colorFG_F:tuple[int, int, int]=None, colorBG_F:tuple[int, int, int]=None,
        borderStyle:int=None, borderChar:str=None, borderStyleFocused:int=None, borderCharFocused:str=None,
        borderFG:tuple[int, int, int]=None, borderBG:tuple[int, int, int]=None, borderFG_F:tuple[int, int, int]=None, borderBG_F:tuple[int, int, int]=None,
        headerLines:int=0, headerTextWrap:int=None, headerTextJust:int=None,
        headerFG:tuple[int, int, int]=None, headerBG:tuple[int, int, int]=None, headerFG_F:tuple[int, int, int]=None, headerBG_F:tuple[int, int, int]=None,
        )->DisplayTile:
        """
        Creates, configures, and registers a new DisplayTile.

        The tile is validated to ensure it fits within the terminal viewport,
        then initialized with the specified text, color, border, and header
        settings before being added to the terminal's tile collection.

        Args:
            x (int): Tile origin column (1-based).
            y (int): Tile origin row (1-based).
            width (int): Tile width in characters.
            height (int): Tile height in rows.

            visible (bool, optional): Whether the tile is initially visible.
            canFocus (bool, optional): Whether the tile can be focused.

            textWrap (int, optional): Text wrapping mode. Style.Wrap.WRAP or Style.Wrap.NOWRAP.
            textJust (int, optional): Text justification mode. Style.Justify.LJUST, Style.Justify.CENTERED, or Style.Justify.RJUST.
            sizeMode (int, optional): Text buffer sizing mode. Style.Size.FIXED or Style.Size.SCROLLING.

            colorFG (tuple[int, int, int], optional): Text foreground RGB color.
            colorBG (tuple[int, int, int], optional): Text background RGB color.
            colorFG_F (tuple[int, int, int], optional): Focused text foreground RGB color. Defaults to `colorFG`.
            colorBG_F (tuple[int, int, int], optional): Focused text background RGB color. Defaults to `colorBG`.

            borderStyle (int, optional): Must be one of Border.BORDER_STYLES.
            borderChar (str, optional): Custom border character set. Overrides `borderStyle`.
            borderStyleFocused (int, optional): Border style used while focused. Defaults to `borderStyle`.
            borderCharFocused (str, optional): Custom focused border character set. Overrides `borderStyleFocused`. Defaults to `borderChar`.

            borderFG (tuple[int, int, int], optional): Border foreground RGB color.
            borderBG (tuple[int, int, int], optional): Border background RGB color.
            borderFG_F (tuple[int, int, int], optional): Focused border foreground RGB color. Defaults to `borderFG`.
            borderBG_F (tuple[int, int, int], optional): Focused border background RGB color. Defaults to `borderBG`.

            headerLines (int, optional): Number of header rows.
            headerTextWrap (int, optional): Header text wrapping mode. Style.Wrap.WRAP or Style.Wrap.NOWRAP.
            headerTextJust (int, optional): Header text justification mode. Style.Justify.LJUST, Style.Justify.CENTERED, or Style.Justify.RJUST.

            headerFG (tuple[int, int, int], optional): Header foreground RGB color.
            headerBG (tuple[int, int, int], optional): Header background RGB color.
            headerFG_F (tuple[int, int, int], optional): Focused header foreground RGB color. Defaults to `headerFG`.
            headerBG_F (tuple[int, int, int], optional): Focused header background RGB color. Defaults to `headerBG`.

        Returns:
            DisplayTile: The newly created DisplayTile instance.
        """
        #check dimensions
        if x <= 0 or x >= self.cols or y <= 0 or y >= self.rows:
            raise ValueError(f"DisplayTile origin is not contained by terminal ({x}, {y})")
        elif x + width - 1 > self.cols:
            raise ValueError(f"DisplayTile exceeds terminal boundary (X-axis) {x + width - 1} > {self.cols}")
        elif y + height - 1 > self.rows:
            raise ValueError(f"DisplayTile exceeds terminal boundary (Y-axis) {y + height - 1} > {self.rows}")

        tile = TerminalTiler.DisplayTile(
            write_func=self._write,
            merge_func=self._mergeBorders,
            x=x,
            y=y,
            width=width,
            height=height,
            visible=visible,
            canFocus=canFocus,
            textWrap=textWrap,
            textJust=textJust,
            sizeMode=sizeMode,
            colorFG=colorFG,
            colorBG=colorBG,
            colorFG_F=colorFG_F,
            colorBG_F=colorBG_F,
            border=TerminalTiler.Border(
                style=borderStyle,
                charset=borderChar,
                colorFG=borderFG,
                colorBG=borderBG,
                style_F=borderStyleFocused,
                charset_F=borderCharFocused,
                colorFG_F=borderFG_F,
                colorBG_F=borderBG_F
            ),
            header=TerminalTiler.Header(
                lines=headerLines,
                textWrap=headerTextWrap,
                textJust=headerTextJust,
                colorFG=headerFG,
                colorBG=headerBG,
                colorFG_F=headerFG_F,
                colorBG_F=headerBG_F
            )
        )
        self.tiles.append(tile)
        return tile

    def addInputTile(self,
        x:int, y:int, width:int, height:int,
        visible:bool=True,
        inputFG:tuple[int, int, int]=None, inputBG:tuple[int, int, int]=None, inputFG_F:tuple[int, int, int]=None, inputBG_F:tuple[int, int, int]=None,
        prompt:str="",
        promptFG:tuple[int, int, int]=None, promptBG:tuple[int, int, int]=None, promptFG_F:tuple[int, int, int]=None, promptBG_F:tuple[int, int, int]=None,
        borderStyle:int=None, borderChar:str=None, borderStyleFocused:int=None, borderCharFocused:str=None,
        borderFG:tuple[int, int, int]=None, borderBG:tuple[int, int, int]=None, borderFG_F:tuple[int, int, int]=None, borderBG_F:tuple[int, int, int]=None
        )->InputTile:
        """
        Creates, configures, and registers a new InputTile.

        The tile is validated to ensure it fits within the terminal viewport,
        then initialized with the specified prompt, colors, and border settings
        before being added to the terminal's tile collection.

        Args:
            x (int): InputTile origin column (1-based).
            y (int): InputTile origin row (1-based).
            width (int): InputTile width in characters.
            height (int): InputTile height in rows.
            visible (bool): Whether the InputTile is initially visible.

            inputFG (tuple[int, int, int], optional): Input foreground RGB color.
            inputBG (tuple[int, int, int], optional): Input background RGB color.
            inputFG_F (tuple[int, int, int], optional): Focused input foreground RGB color. Defaults to `inputFG`.
            inputBG_F (tuple[int, int, int], optional): Focused input background RGB color. Defaults to `inputBG`.

            prompt (str): Prompt displayed before the input text.

            promptFG (tuple[int, int, int], optional): Prompt foreground RGB color.
            promptBG (tuple[int, int, int], optional): Prompt background RGB color.
            promptFG_F (tuple[int, int, int], optional): Focused prompt foreground RGB color. Defaults to `promptFG`.
            promptBG_F (tuple[int, int, int], optional): Focused prompt background RGB color. Defaults to `promptBG`.

            borderStyle (int, optional): Border style constant.
            borderChar (str, optional): Custom border character set. Overrides `borderStyle`.
            borderStyleFocused (int, optional): Border style used while focused. Defaults to `borderStyle`.
            borderCharFocused (str, optional): Custom focused border character set. Overrides `borderStyleFocused`. Defaults to `borderChar`.

            borderFG (tuple[int, int, int], optional): Border foreground RGB color.
            borderBG (tuple[int, int, int], optional): Border background RGB color.
            borderFG_F (tuple[int, int, int], optional): Focused border foreground RGB color. Defaults to `borderFG`.
            borderBG_F (tuple[int, int, int], optional): Focused border background RGB color. Defaults to `borderBG`.

        Returns:
            InputTile: Newly created InputTile instance.
        """
        #check dimensions
        if x <= 0 or x >= self.cols or y <= 0 or y >= self.rows:
            raise ValueError(f"InputTile origin is not contained by terminal ({x}, {y})")
        elif x + width - 1 > self.cols:
            raise ValueError(f"InputTile exceeds terminal boundary (X-axis) {x + width - 1} > {self.cols}")
        elif y + height - 1 > self.rows:
            raise ValueError(f"InputTile exceeds terminal boundary (Y-axis) {y + height - 1} > {self.rows}")

        tile = TerminalTiler.InputTile(
            write_func=self._write,
            merge_func=self._mergeBorders,
            exit_event=self.exit,
            x=x,
            y=y,
            width=width,
            height=height,
            visible=visible,
            inputFG=inputFG,
            inputBG=inputBG,
            inputFG_F=inputFG_F,
            inputBG_F=inputBG_F,
            prompt=prompt,
            promptFG=promptFG,
            promptBG=promptBG,
            promptFG_F=promptFG_F,
            promptBG_F=promptBG_F,
            border=TerminalTiler.Border(
                style=borderStyle,
                charset=borderChar,
                colorFG=borderFG,
                colorBG=borderBG,
                style_F=borderStyleFocused,
                charset_F=borderCharFocused,
                colorFG_F=borderFG_F,
                colorBG_F=borderBG_F
            )
        )
        self.tiles.append(tile)
        return tile

    def addProgressBar(self,
        max:int,
        barChar:str,
        x:int, y:int, width:int,
        visible:bool=False,
        colorFG:tuple[int, int, int]=None, colorBG:tuple[int, int, int]=None,
        borderStyle:int=None, borderChar:str=None,
        borderFG:tuple[int, int, int]=None, borderBG:tuple[int, int, int]=None,
        textOverlay:str="", textLeft:str="", textRight:str="")->ProgressBar:
        """
        Creates, configures, and registers a new ProgressBar.

        The progress bar is validated to ensure it fits within the terminal
        viewport, then initialized with the specified appearance and border
        settings before being added to the terminal's tile collection.

        The bar is rendered as follows:
            | textLeft | barChar * N | textOverlay | barChar * N | textRight |

        Three text sections will be rendered if set:
                textLeft    - Rendered on left side of ProgressBar.
                textOverlay - Overlay text is centered within the bar and replaces the underlying bar characters.
                textRight   - Rendered on right side of ProgressBar.

        These sections may be formatted using the following placeholders:

            {VALUE}     - Current progress value.
            {MAX}       - Maximum progress value.
            {PERCENT}   - Progress percentage (0-100).
            {RATIO}     - Progress ratio (0.0-1.0).
            {AVG_ITTS}  - Average iterations per second.
            {AVG_TIME}  - Average time per iteration.
            {ELAPSED}   - Time elapsed since start.
            {REMAINING} - Estimated time remaining.

        Time placeholders ({AVG_TIME}, {ELAPSED}, and {REMAINING}) support
        custom time format specifiers:

            H    - Hours.
            HH   - Zero-padded hours.
            M    - Minutes.
            MM   - Zero-padded minutes.
            S    - Seconds.
            SS   - Zero-padded seconds.
            m    - Tenths.
            mm   - Hundredths.
            mmm  - Milliseconds.

        Default time format is MM:SS.

        Args:
            x (int): ProgressBar origin column (1-based).
            y (int): ProgressBar origin row (1-based).
            width (int): ProgressBar width in characters.

            visible (bool): Whether the ProgressBar is initially visible.

            max (int): Maximum progress value representing 100% completion.
            barChar (str): Character(s) used to draw the filled portion of the progress bar.
            textOverlay (str, optional): Overlay text is centered within the bar and replaces the underlying bar characters.
            textLeft (str, optional): Rendered on left side of ProgressBar.
            textRight (str, optional): Rendered on right side of ProgressBar.

            colorFG (tuple[int, int, int], optional): Progress bar foreground RGB color.
            colorBG (tuple[int, int, int], optional): Progress bar background RGB color.

            borderStyle (int, optional): Border style constant.
            borderChar (str, optional): Custom border character set. Overrides `borderStyle`.

            borderFG (tuple[int, int, int], optional): Border foreground RGB color.
            borderBG (tuple[int, int, int], optional): Border background RGB color.

        Returns:
            ProgressBar: The newly created ProgressBar instance.
        """
        height = 1
        if borderStyle:
            if borderStyle != TerminalTiler.Border.NO_BORDER:
                height = 3
        #check dimensions
        if x <= 0 or x >= self.cols or y <= 0 or y >= self.rows:
            raise ValueError(f"ProgressBar origin is not contained by terminal ({x}, {y})")
        elif x + width - 1 > self.cols:
            raise ValueError(f"ProgressBar exceeds terminal boundary (X-axis) {x + width - 1} > {self.cols}")
        elif y + height - 1 > self.rows:
            raise ValueError(f"ProgressBar exceeds terminal boundary (Y-axis) {y + height - 1} > {self.rows}")
        elif max <= 0:
            raise ValueError(f"Max bar value must be > 0")

        tile = TerminalTiler.ProgressBar(
            write_func=self._write,
            merge_func=self._mergeBorders,
            max=max,
            x=x,
            y=y,
            width=width,
            height=height,
            visible=visible,
            colorFG=colorFG,
            colorBG=colorBG,
            border=TerminalTiler.Border(
                style=borderStyle,
                charset=borderChar,
                colorFG=borderFG,
                colorBG=borderBG,
            ),
            barChar=barChar,
            textLeft=textLeft,
            textRight=textRight,
            textOverlay=textOverlay
        )
        self.tiles.append(tile)
        return tile

    def addAlert(self,
        x:int, y:int, width:int, height:int,
        text:str="", textWrap:int=None, textJust:int=None,
        colorFG:tuple[int, int, int]=None, colorBG:tuple[int, int, int]=None,
        borderStyle:int=None, borderChar:str=None,
        borderFG:tuple[int, int, int]=None, borderBG:tuple[int, int, int]=None)->Alert:
        """
        Creates, configures, and registers a new Alert.

        The alert is validated to ensure it fits within the terminal viewport,
        then initialized with the specified text, colors, and border settings
        before being added to the terminal's tile collection.

        Args:
            x (int): Alert origin column (1-based).
            y (int): Alert origin row (1-based).
            width (int): Alert width in characters.
            height (int): Alert height in rows.

            text (str, optional): Initial alert text.
            textWrap (int, optional): Text wrapping mode. Style.Wrap.WRAP or Style.Wrap.NOWRAP.
            textJust (int, optional): Text justification mode. Style.Justify.LJUST, Style.Justify.CENTERED, or Style.Justify.RJUST.

            colorFG (tuple[int, int, int], optional): Alert foreground RGB color.
            colorBG (tuple[int, int, int], optional): Alert background RGB color.

            borderStyle (int, optional): Border style constant.
            borderChar (str, optional): Custom border character set. Overrides `borderStyle`.

            borderFG (tuple[int, int, int], optional): Border foreground RGB color.
            borderBG (tuple[int, int, int], optional): Border background RGB color.

        Returns:
            Alert: The newly created Alert instance.
        """
        #check dimensions
        if x <= 0 or x >= self.cols or y <= 0 or y >= self.rows:
            raise ValueError(f"Alert origin is not contained by terminal ({x}, {y})")
        elif x + width - 1 > self.cols:
            raise ValueError(f"Alert exceeds terminal boundary (X-axis) {x + width - 1} > {self.cols}")
        elif y + height - 1 > self.rows:
            raise ValueError(f"Alert exceeds terminal boundary (Y-axis) {y + height - 1} > {self.rows}")

        tile = TerminalTiler.Alert(
            write_func=self._write,
            overlap_func=self._getIntersectingElements,
            popup_lock=self.popup,
            exit_event=self.exit,
            wait_con=self.wait_con,
            x=x,
            y=y,
            width=width,
            height=height,
            textWrap=textWrap,
            textJust=textJust,
            colorFG=colorFG,
            colorBG=colorBG,
            border=TerminalTiler.Border(
                style=borderStyle,
                charset=borderChar,
                colorFG=borderFG,
                colorBG=borderBG,
            ),
            text=text
        )
        self.tiles.append(tile)
        return tile

    def addMessageBox(self,
        x:int, y:int, width:int, height:int,
        text:str="", textWrap:int=None, textJust:int=None,
        colorFG:tuple[int, int, int]=None, colorBG:tuple[int, int, int]=None,
        borderStyle:int=None, borderChar:str=None,
        borderFG:tuple[int, int, int]=None, borderBG:tuple[int, int, int]=None,
        headerText="", headerLines:int=0, headerTextWrap:int=None, headerTextJust:int=None)->MessageBox:
        """
        Creates and registers a new MessageBox in the terminal layout.

        Performs boundary validation against the terminal size to ensure
        the tile fits within the visible viewport. Then constructs a MessageBox
        instance with the specified border and header configuration stores it in self.tiles[].

        Args:
            x (int): MessageBox origin column (1-based).
            y (int): MessageBox origin row (1-based).
            width (int): MessageBox width in characters.
            height (int): MessageBox height in rows.
            text (str): MessageBox text.
            textWrap (int, optional): Text wrap mode. Style.Wrap.WRAP or Style.Wrap.NOWRAP.
            textJust (int, optional): Text justify mode. Style.Justify.LJUST, Style.Justify.CENTERED, or Style.Justify.RJUST.
            borderStyle (int, optional): Border style constant.
            borderChar (str, optional): Custom border character.
            headerText (str, optional): MessageBox header text.
            headerLines (int, optional): Number of header rows.
            headerTextWrap (int, optional): Header text wrap mode. Style.Wrap.WRAP or Style.Wrap.NOWRAP.
            headerTextJust (int, optional): Header text justify mode. Style.Justify.LJUST, Style.Justify.CENTERED, or Style.Justify.RJUST.
            headerBorder (bool): Whether header has its own border.

        Returns:
            MessageBox: MessageBox object.
        """
        #check dimensions
        if x <= 0 or x >= self.cols or y <= 0 or y >= self.rows:
            raise ValueError(f"MessageBox origin is not contained by terminal ({x}, {y})")
        elif x + width - 1 > self.cols:
            raise ValueError(f"MessageBox exceeds terminal boundary (X-axis) {x + width - 1} > {self.cols}")
        elif y + height - 1 > self.rows:
            raise ValueError(f"MessageBox exceeds terminal boundary (Y-axis) {y + height - 1} > {self.rows}")

        tile = TerminalTiler.MessageBox(
            write_func=self._write,
            overlap_func=self._getIntersectingElements,
            popup_lock=self.popup,
            exit_event=self.exit,
            wait_con=self.wait_con,
            text=text,
            headerText=headerText,
            x=x,
            y=y,
            width=width,
            height=height,
            textWrap=textWrap,
            textJust=textJust,
            colorFG=colorFG,
            colorBG=colorBG,
            border=TerminalTiler.Border(
                style=borderStyle,
                charset=borderChar,
                colorFG=borderFG,
                colorBG=borderBG,
            ),
            header=TerminalTiler.Header(
                lines=headerLines,
                textWrap=headerTextWrap,
                textJust=headerTextJust
            )
        )
        self.tiles.append(tile)
        return tile

    def addTable(self,
        x:int, y:int, width:int, height:int,
        visible:bool=False, canFocus:bool=False,
        textWrap:int=None, textJust:int=None,
        colorFG:tuple[int, int, int]=None, colorBG:tuple[int, int, int]=None, colorFG_F:tuple[int, int, int]=None, colorBG_F:tuple[int, int, int]=None,
        borderStyle:int=None, borderChar:str=None, borderStyleFocused:int=None, borderCharFocused:str=None,
        borderFG:tuple[int, int, int]=None, borderBG:tuple[int, int, int]=None, borderFG_F:tuple[int, int, int]=None, borderBG_F:tuple[int, int, int]=None,
        headerLines:int=0, headerTextWrap:int=None, headerTextJust:int=None,
        headerFG:tuple[int, int, int]=None, headerBG:tuple[int, int, int]=None, headerFG_F:tuple[int, int, int]=None, headerBG_F:tuple[int, int, int]=None,
        )->Table:
        """
        Creates, configures, and registers a new Table.

        The table is validated to ensure it fits within the terminal viewport,
        then initialized with the specified text, color, border, and header
        settings before being added to the terminal's tile collection.

        Args:
            x (int): Table origin column (1-based).
            y (int): Table origin row (1-based).
            width (int): Table width in characters.
            height (int): Table height in rows.
            visible (bool): Whether the table is initially visible.
            canFocus (bool): Whether the table can receive keyboard focus.

            textWrap (int, optional): Default text wrapping mode for table cells. Style.Wrap.WRAP or Style.Wrap.NOWRAP.
            textJust (int, optional): Default text justification mode for table cells. Style.Justify.LJUST, Style.Justify.CENTERED, or Style.Justify.RJUST.

            colorFG (tuple[int, int, int], optional): Default cell foreground RGB color.
            colorBG (tuple[int, int, int], optional): Default cell background RGB color.
            colorFG_F (tuple[int, int, int], optional): Default focused cell foreground RGB color. Defaults to `colorFG`.
            colorBG_F (tuple[int, int, int], optional): Default focused cell background RGB color. Defaults to `colorBG`.

            borderStyle (int, optional): Border style constant.
            borderChar (str, optional): Custom border character set. Overrides `borderStyle`.
            borderStyleFocused (int, optional): Border style used while focused. Defaults to `borderStyle`.
            borderCharFocused (str, optional): Custom focused border character set. Overrides `borderStyleFocused`. Defaults to `borderChar`.

            borderFG (tuple[int, int, int], optional): Border foreground RGB color.
            borderBG (tuple[int, int, int], optional): Border background RGB color.
            borderFG_F (tuple[int, int, int], optional): Focused border foreground RGB color. Defaults to `borderFG`.
            borderBG_F (tuple[int, int, int], optional): Focused border background RGB color. Defaults to `borderBG`.

            headerLines (int, optional): Number of header rows.
            headerTextWrap (int, optional): Header text wrapping mode. Style.Wrap.WRAP or Style.Wrap.NOWRAP.
            headerTextJust (int, optional): Header text justification mode. Style.Justify.LJUST, Style.Justify.CENTERED, or Style.Justify.RJUST.

            headerFG (tuple[int, int, int], optional): Header foreground RGB color.
            headerBG (tuple[int, int, int], optional): Header background RGB color.
            headerFG_F (tuple[int, int, int], optional): Focused header foreground RGB color. Defaults to `headerFG`.
            headerBG_F (tuple[int, int, int], optional): Focused header background RGB color. Defaults to `headerBG`.

        Returns:
            Table: The newly created Table instance.
        """
        #check dimensions
        if x <= 0 or x >= self.cols or y <= 0 or y >= self.rows:
            raise ValueError(f"Table origin is not contained by terminal ({x}, {y})")
        elif x + width - 1 > self.cols:
            raise ValueError(f"Table exceeds terminal boundary (X-axis) {x + width - 1} > {self.cols}")
        elif y + height - 1 > self.rows:
            raise ValueError(f"Table exceeds terminal boundary (Y-axis) {y + height - 1} > {self.rows}")

        tile = TerminalTiler.Table(
            write_func=self._write,
            merge_func=self._mergeBorders,
            x=x,
            y=y,
            width=width,
            height=height,
            visible=visible,
            canFocus=canFocus,
            textWrap=textWrap,
            textJust=textJust,
            colorFG=colorFG,
            colorBG=colorBG,
            colorFG_F=colorFG_F,
            colorBG_F=colorBG_F,
            border=TerminalTiler.Border(
                style=borderStyle,
                charset=borderChar,
                colorFG=borderFG,
                colorBG=borderBG,
                style_F=borderStyleFocused,
                charset_F=borderCharFocused,
                colorFG_F=borderFG_F,
                colorBG_F=borderBG_F
            ),
            header=TerminalTiler.Header(
                lines=headerLines,
                textWrap=headerTextWrap,
                textJust=headerTextJust,
                colorFG=headerFG,
                colorBG=headerBG,
                colorFG_F=headerFG_F,
                colorBG_F=headerBG_F
            )
        )
        self.tiles.append(tile)
        return tile

    def _getIntersectingElements(self, tile)->list:
        """
        Get all tiles that geometrically overlap the given tile.

        Args:
            tile: The tile to test against.

        Returns:
            list: A list of intersecting tiles.
        """
        overlaps = []
        for t in self.tiles:
            if not t is tile:
                if tile.x < t.x + t.width and tile.x + tile.width > t.x and tile.y < t.y + t.height and tile.y + tile.height > t.y:
                    overlaps.append(t)

        return overlaps

    def _getEdges(self, tile):
        """
        Returns the border edge segments of a tile.

        Args:
            tile: Tile element.

        Returns:
            tuple[list[tuple[int, int, int]], list[tuple[int, int, int]]]:
                A tuple containing:
                    - Vertical edges as `(x, y1, y2)`.
                    - Horizontal edges as `(y, x1, x2)`.
        """
        x1, y1, x2, y2 = tile.getRect()

        vertical = [
            (x1, y1, y2),
            (x2, y1, y2),
        ]

        horizontal = [
            (y1, x1, x2),
            (y2, x1, x2),
        ]

        # header separator line
        if isinstance(tile, (TerminalTiler.DisplayTile, TerminalTiler.InputTile)):
            t = tile
        else:
            t = tile.displayTile
        header_rows = t.header.rows if isinstance(t, TerminalTiler.DisplayTile) else 0
        if header_rows > 0:
            horizontal.append((y1 + header_rows + 1, x1, x2))

        # table cell separators
        if isinstance(tile, TerminalTiler.Table):
            x = t.x
            y = t.y + ((header_rows + 1) if header_rows > 0 else 0)
            for c in tile.col_list:
                x += c.size + 1
                vertical.append((x, y1, y2))
            for r in tile.row_list:
                y += r.size + 1
                horizontal.append((y, x1, x2))

        return vertical, horizontal

    def _getIntersectionCoords(self, a, b)->list[tuple[int, int]]:
        """
        Returns all border intersection points between two tiles, including
        header separator intersections.

        Args:
            a: Foreground tile.
            b: Background tile.

        Returns:
            list[tuple[int, int]]: Unique `(x, y)` coordinates where visible
            border segments intersect.
        """
        points = set()

        a_vertical, a_horizontal = self._getEdges(a)
        b_vertical, b_horizontal = self._getEdges(b)

        rax1, ray1, rax2, ray2 = a.getRect()

        # vertical vs horizontal
        for x, ay1, ay2 in a_vertical:
            for y, bx1, bx2 in b_horizontal:
                if bx1 <= x <= bx2 and ay1 <= y <= ay2:
                    if x in (rax1, rax2) or y in (ray1, ray2):
                        points.add((x, y))

        for x, by1, by2 in b_vertical:
            for y, ax1, ax2 in a_horizontal:
                if ax1 <= x <= ax2 and by1 <= y <= by2:
                    if x in (rax1, rax2) or y in (ray1, ray2):
                        points.add((x, y))

        return list(points)

    def _getJunctionChar(self, a, b, p:tuple[int, int], charset:Border.Charset) -> str:
        """
        Determines the box-drawing character to render at the intersection of two
        tile borders.

        The foreground tile (`a`) is drawn over the background tile (`b`). Border
        segments from `b` are only used where they do not conflict with visible
        border segments from `a`.

        Args:
            a: Foreground tile.
            b: Background tile.
            p (tuple[int, int]): The `(x, y)` coordinate of the border intersection.
            charset (Border.Charset): Border character set used to select the
                appropriate junction glyph.

        Returns:
            str: The box-drawing character representing the visible border
            connections at the intersection, or ``None`` if the resulting
            combination does not correspond to a supported junction.
        """
        ax1, ay1, ax2, ay2 = a.getRect()
        bx1, by1, bx2, by2 = b.getRect()
        ix, iy = p

        a_vertical, a_horizontal = self._getEdges(a)
        b_vertical, b_horizontal = self._getEdges(b)
        # raise(Exception(f"{a_vertical, a_horizontal, b_vertical, b_horizontal}"))

        a_up = a_down = a_left = a_right = False
        b_up = b_down = b_left = b_right = False

        for x, y1, y2 in a_vertical:
            if ix == x and y1 <= iy <= y2:
                a_up |= iy > y1
                a_down |= iy < y2

        for y, x1, x2 in a_horizontal:
            if iy == y and x1 <= ix <= x2:
                a_left |= ix > x1
                a_right |= ix < x2

        for x, y1, y2 in b_vertical:
            if ix == x and y1 <= iy <= y2:
                b_up |= iy > y1
                b_down |= iy < y2

        for y, x1, x2 in b_horizontal:
            if iy == y and x1 <= ix <= x2:
                b_left |= ix > x1
                b_right |= ix < x2

        # A is above B
        if ay2 <= by2 and (iy < ay1 or iy == ay2):
            b_up &= not (a_left or a_right)

        # A is below B
        if ay1 >= by1 and (iy > ay2 or iy == ay1):
            b_down &= not (a_left or a_right)

        # A is left of B
        if ax2 <= bx2 and (ix < ax1 or ix == ax2):
            b_left &= not (a_up or a_down)

        # A is right of B
        if ax1 >= bx1 and (ix > ax2 or ix == ax1):
            b_right &= not (a_up or a_down)

        match (a_up or b_up, a_down or b_down, a_left or b_left, a_right or b_right):
            case (False, False, True,  True):
                char = charset.lineH
            case (True,  True,  False, False):
                char = charset.lineV
            case (True,  True,  False, True):
                char = charset.junctionVE
            case (True,  True,  True,  False):
                char = charset.junctionVW
            case (False, True,  True,  True):
                char = charset.junctionHS
            case (True,  False, True,  True):
                char = charset.junctionHN
            case (True,  True,  True,  True):
                char = charset.junctionAll
            case _:
                char = None  # invalid

        return char

    def _mergeBorders(self, tile):
        """
        Merges compatible borders between a tile and any visible intersecting tiles.

        The supplied tile is treated as the foreground tile. For each visible
        intersecting tile, compatible border styles and matching border colors are
        required before any merge is attempted. Every border intersection is then
        located and replaced with the appropriate border junction character.

        Args:
            tile: The foreground element whose border is being merged.
        """
        if isinstance(tile, (TerminalTiler.DisplayTile, TerminalTiler.InputTile)):
            a = tile
        else:
            a = tile.displayTile

        # check if border
        if a.border.style != TerminalTiler.Border.NO_BORDER:
            a_fg = a.border.colorFG_F if tile.focused else a.border.colorFG
            a_bg = a.border.colorBG_F if tile.focused else a.border.colorBG
            a_charset = a.border.charset_F if tile.focused else a.border.charset

            tiles = self._getIntersectingElements(tile)
            for t in tiles:
                # check if visible
                if t.visible:
                    if isinstance(t, (TerminalTiler.DisplayTile, TerminalTiler.InputTile)):
                        b = t
                    else:
                        b = t.displayTile

                    b_charset = b.border.charset_F if t.focused else b.border.charset
                    # check if border style matches
                    if a_charset.canMerge(b_charset):
                        b_fg = b.border.colorFG_F if t.focused else b.border.colorFG
                        b_bg = b.border.colorBG_F if t.focused else b.border.colorBG
                        # check if color matches
                        if a_fg == b_fg and a_bg == b_bg:
                            coords = self._getIntersectionCoords(tile, t)
                            for p in coords:
                                char = self._getJunctionChar(tile, t, p, a_charset)
                                if char:
                                    self._write(f"\x1b[{p[1]};{p[0]}H{char}".encode(), a_fg, a_bg)

    def _handleInput(self, key:str):
        """
        Handles keyboard input for tile navigation and scrolling.
        """
        if key == TerminalTiler.Keyboard.KEY_CTRL_C:
            self.close()

        # if alert is not active, handle input
        elif self.popup.acquire(blocking=False):
            if (key == self.waitKey or self.waitKey == TerminalTiler.Keyboard.KEY_ANY):
                self.waitKey = None
                with self.wait_con:
                    self.wait_con.notify_all()

            elif key == TerminalTiler.Keyboard.KEY_TAB:
                self._write("\033[?25l".encode()) # hide cursor
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

                # show cursor if focused element is inputTile
                if self.focusedIndex != -1:
                    if isinstance(self.tiles[self.focusedIndex], TerminalTiler.InputTile):
                        self._write("\033[?25h".encode()) # show cursor

            else:
                # send to element
                if self.focusedIndex >= 0:
                    self.tiles[self.focusedIndex].handleInput(key)

            self.popup.release()
        # if popup is active, send input to popup element
        else:
            for t in self.tiles:
                if t.visible and (isinstance(t, self.Alert) or isinstance(t, self.MessageBox)):
                    t.handleInput(key)
                    break

    def clearScreen(self):
        """
        Clears terminal screen.
        """
        self._write("\x1b[2J".encode())

    def _write(self, text:bytes, fg_color:tuple[int, int, int]=None, bg_color:tuple[int, int, int]=None):
        """
        Writes text to the terminal.

        Args:
            text (bytes): Terminal output to write.
            fg_color (tuple[int, int, int], optional): RGB foreground color.
            bg_color (tuple[int, int, int], optional): RGB background color.
        """
        # check if threads are exiting
        if self.isAlive():
            # check if popup is active
            with self.popup:
                # check if another thread is writing
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
            # set flag
            self.exit.set()
            # reset cursor
            maxY = max(e.y + e.height for e in self.tiles)
            os.write(self.stdout_FDI.real_fd, f"\x1b[{maxY};1H".encode()) # position
            os.write(self.stdout_FDI.real_fd, "\033[?25h".encode()) # show
            # kill threads
            self.stdout_FDI.close()
            # notify waiting threads
            with self.wait_con:
                self.wait_con.notify_all()

    def focus(self, element):
        """
        Sets focus to provided element. Element must be valid and able to be focused.

        Args:
            element: Element to focus. Must be OutputTile, InputTile, or Table.
        """
        if isinstance(element, (TerminalTiler.DisplayTile, TerminalTiler.InputTile, TerminalTiler.Table)):
            if element.canFocus:
                index = None
                for i, t in enumerate(self.tiles):
                    if t is element:
                        index = i
                        break
                if not index is None:
                    self._write("\033[?25l".encode()) # hide cursor
                    # clear old focus
                    if 0 <= self.focusedIndex and self.focusedIndex < len(self.tiles):
                        self.tiles[self.focusedIndex].focused = False
                        self.tiles[self.focusedIndex].show()

                    # set index
                    self.focusedIndex = index

                    # apply or reset
                    if self.focusedIndex < len(self.tiles):
                        self.tiles[self.focusedIndex].focused = True
                        self.tiles[self.focusedIndex].show()
                    else:
                        self.focusedIndex = -1

                    # show cursor if focused element is inputTile
                    if self.focusedIndex != -1:
                        if isinstance(self.tiles[self.focusedIndex], TerminalTiler.InputTile):
                            self._write("\033[?25h".encode()) # show cursor

    def waitForKey(self, key:str):
        """
        Blocks current thread until the specified key is pressed.

        Args:
            key (str):
                Value stored in self.waitKey.
        """
        self.waitKey = key
        # wait
        with self.wait_con:
            self.wait_con.wait()