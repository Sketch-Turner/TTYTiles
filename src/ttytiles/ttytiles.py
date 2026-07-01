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

        def __init__(self, lines:int=0, textWrap:int=0, textJust:int=0, hasBorder:bool=False):
            """
            Initializes the header buffer and display configuration.

            Args:
                lines (int): Maximum number of text rows stored.
                textWrap (int): Text wrap mode. Style.Wrap.WRAP or Style.Wrap.NOWRAP.
                textJust (int): Text justify mode. Style.Justify.LJUST, Style.Justify.CENTERED, or Style.Justify.RJUST.
                hasBorder (bool): Render border between header and text?
            """
            self.textWrap = textWrap if textWrap in TerminalTiler.Style.Wrap.STYLES else TerminalTiler.Style.Wrap.NOWRAP
            self.textJust = textJust if textJust in TerminalTiler.Style.Justify.STYLES else -1
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

    class Style:
        class Wrap:
            """
            Text wrapping.

            STYLES:
            - WRAP
            - NOWRAP
            """
            NOWRAP = 0
            WRAP = 1
            STYLES = {NOWRAP, WRAP}

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
        def __init__(self, write_func, x:int, y:int, width:int, height:int, visible:bool, canFocus:bool, textWrap:int, textJust:int, sizeMode:int, border:"TerminalTiler.Border", header:"TerminalTiler.Header"):
            """
            Initializes a DisplayTile UI component that represents a bordered
            terminal region with an optional header and scrollable text buffer.

            Args:
                write_func: Used to write to terminal.
                x (int): Column position of the tile (1-based terminal coords).
                y (int): Row position of the tile (1-based terminal coords).
                width (int): Total width of the tile including borders.
                height (int): Total height of the tile including borders.
                visible (bool): Should the item be rendered?
                canFocus (bool): Can the item be focused?
                textWrap (int): Text wrap mode. Style.Wrap.WRAP or Style.Wrap.NOWRAP.
                textJust (int): Text justify mode. Style.Justify.LJUST, Style.Justify.CENTERED, or Style.Justify.RJUST.
                sizeMode (int): Text buffer sizing. Style.Size.FIXED or Style.Size.SCROLLING.
                border (TerminalTiler.Border): Border style/renderer instance.
                header (TerminalTiler.Header): Header configuration and buffer.
            """
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

            # set size of buffers
            self.resize()

            self.visible = visible
            self.focused = False
            self.canFocus = canFocus
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
            if self.header.hasBorder:
                self.ty += 1
                self.rows -= 1

            if self.sizeMode == TerminalTiler.Style.Size.SCROLLING:
                self.cols -= 2

            if self.sizeMode == TerminalTiler.Style.Size.FIXED:
                self.text = deque(maxlen=self.rows)
            else:
                self.text = []
            self.tIndex = 0

        def drawBorder(self):
            """
            Draws:
                - Left and right vertical border lines
                - Top border line
                - Optional header separator (middle border)
                - Bottom border line
            """
            if self.focused:
                color_fg = self.colors.get("BORDER_FG_F", None)
                color_bg = self.colors.get("BORDER_BG_F", None)
            else:
                color_fg = self.colors.get("BORDER_FG", None)
                color_bg = self.colors.get("BORDER_BG", None)

            if self.border.style != TerminalTiler.Border.NO_BORDER:
                for row in range(self.y + 1, self.y + self.height):
                    self.write(f"\x1b[{row};{self.x}H{self.border.charset.lineV}".encode(), color_fg, color_bg)
                    self.write(f"\x1b[{row};{self.x + self.width - 1}H{self.border.charset.lineV}".encode(), color_fg, color_bg)

                self.write(f"\x1b[{self.y};{self.x}H{self.border.getTop(self.width)}".encode(), color_fg, color_bg)
                if self.header.hasBorder:
                    self.write(f"\x1b[{self.y + self.header.rows + 1};{self.x}H{self.border.getMiddle(self.width)}".encode(), color_fg, color_bg)
                self.write(f"\x1b[{self.y + self.height - 1};{self.x}H{self.border.getBottom(self.width)}".encode(), color_fg, color_bg)

                if self.sizeMode == TerminalTiler.Style.Size.SCROLLING:
                    self.drawScrollbarBorder()
                    self.drawScrollbar()

        def drawScrollbarBorder(self):
            """
            Draws the right-side scrollbar border.
            """
            if self.focused:
                color_fg = self.colors.get("BORDER_FG_F", None)
                color_bg = self.colors.get("BORDER_BG_F", None)
            else:
                color_fg = self.colors.get("BORDER_FG", None)
                color_bg = self.colors.get("BORDER_BG", None)

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
            if self.border.style != TerminalTiler.Border.NO_BORDER:
                cornerBottom = self.border.charset.junctionHN
            self.write(f"\x1b[{self.y + self.height - 1};{self.x + self.width - 3}H{cornerBottom + self.border.charset.lineH + self.border.charset.cornerSE}".encode(), color_fg, color_bg)

        def drawScrollbar(self):
            """
            Renders the scrollbar thumb inside the scrollbar track.
            """
            if self.focused:
                color_fg = self.colors.get("BORDER_FG_F", None)
                color_bg = self.colors.get("BORDER_BG_F", None)
            else:
                color_fg = self.colors.get("BORDER_FG", None)
                color_bg = self.colors.get("BORDER_BG", None)

            bar_top = self.y + self.header.rows
            if self.border.style != TerminalTiler.Border.NO_BORDER:
                bar_top += 1
            if self.header.hasBorder:
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
                self.write(f"\x1b[{bar_top + bar1};{self.x + self.width - 2}H{self.border.charset.boxFull}".encode(), color_fg, color_bg)
            else:
                self.write(f"\x1b[{bar_top + bar1};{self.x + self.width - 2}H{self.border.charset.boxLower}".encode(), color_fg, color_bg)
                self.write(f"\x1b[{bar_top + bar2};{self.x + self.width - 2}H{self.border.charset.boxUpper}".encode(), color_fg, color_bg)

        def drawText(self):
            """
            Renders the visible portion of the text buffer to the terminal.
            """
            if self.focused:
                color_fg = self.colors.get("TEXT_FG_F", None)
                color_bg = self.colors.get("TEXT_BG_F", None)
            else:
                color_fg = self.colors.get("TEXT_FG", None)
                color_bg = self.colors.get("TEXT_BG", None)
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
            text = str(text).replace('\r\n', '\n').replace('\r', '\n')
            for line in text.split('\n'):
                if self.textWrap == TerminalTiler.Style.Wrap.NOWRAP:
                    output = line[:self.cols]
                    self.text.append(self.justify(output, self.textJust, self.cols))
                    self.tIndex = len(self.text) - 1
                elif self.textWrap == TerminalTiler.Style.Wrap.WRAP:
                    for i in range(0, len(line), self.cols):
                        output = line[i:i+self.cols]
                        self.text.append(self.justify(output, self.textJust, self.cols))
                        self.tIndex += len(self.text) - 1

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
            self.drawHeader()

        def drawHeader(self):
            """
            Renders header to terminal.
            """
            if self.focused:
                color_fg = self.colors.get("HEADER_FG_F", None)
                color_bg = self.colors.get("HEADER_BG_F", None)
            else:
                color_fg = self.colors.get("HEADER_FG", None)
                color_bg = self.colors.get("HEADER_BG", None)
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
            self.visible = False
            # hide cursor
            self.write("\033[?25l".encode())
            for i in range(self.height):
                self.write(f"\x1b[{self.y + i};{self.x}H{' ' * self.width}".encode())

    class InputTile:
        """
        A fixed-size terminal input tile supporting interactive text editing.
        """
        def __init__(self, write_func, exit_event:threading.Event, x:int, y:int, width:int, height:int, visible:bool, canFocus:bool, prompt:str, border:"TerminalTiler.Border"):
            """
            Initializes a terminal input tile with a fixed-size grid layout.

            Configures geometry (position, width, height), optional border offsets,
            prompt rendering, and input capacity limits.

            Args:
                write_func: Used to write to terminal.
                exit_event (threading.Event): Exit flag.
                x (int): Column position.
                y (int): Row position.
                width (int): Tile width.
                height (int): Tile height.
                visible (bool): Should the item be rendered?
                canFocus (bool): Can the item be focused?
                prompt (str): Prompt text displayed above input area.
                border (TerminalTiler.Border): Border configuration.
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
            if self.border.style != TerminalTiler.Border.NO_BORDER:
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
            self.canFocus = canFocus
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

            prompt = str(prompt).replace('\r\n', '\n').replace('\r', '\n')
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
            self.visible = True
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
            self.visible = False
            for i in range(self.height):
                self.write(f"\x1b[{self.y + i};{self.x}H{' ' * self.width}".encode())

        def drawText(self):
            """
            Renders prompt to terminal.
            """
            # render text
            if self.focused:
                color_fg = self.colors.get("TEXT_FG_F", None)
                color_bg = self.colors.get("TEXT_BG_F", None)
            else:
                color_fg = self.colors.get("TEXT_FG", None)
                color_bg = self.colors.get("TEXT_BG", None)
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
                color_fg = self.colors.get("BORDER_FG_F", None)
                color_bg = self.colors.get("BORDER_BG_F", None)
            else:
                color_fg = self.colors.get("BORDER_FG", None)
                color_bg = self.colors.get("BORDER_BG", None)

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
                color_fg = self.colors.get("INPUT_FG_F", None)
                color_bg = self.colors.get("INPUT_BG_F", None)
            else:
                color_fg = self.colors.get("INPUT_FG", None)
                color_bg = self.colors.get("INPUT_BG", None)

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

    class ProgressBar:
        """
        A terminal UI region that renders a progress bar.
        """
        def __init__(self, write_func, max:int, x:int, y:int, width:int, height:int, visible:bool, border:"TerminalTiler.Border", barChar:str, barLeft:str, barRight:str):
            """
            Initialize a ProgressBar display tile.

            The progress bar is rendered inside an internal DisplayTile and tracks
            a current value relative to a maximum value. Optional text can be shown
            to the left, right, or overlaid on top of the bar.

            Args:
                write_func (callable): Function used to write output to the display.
                max (int): Maximum progress value representing 100% completion.
                x (int): X-coordinate of the tile.
                y (int): Y-coordinate of the tile.
                width (int): Width of the tile in characters.
                height (int): Height of the tile in characters.
                visible (bool): Whether the tile is initially visible.
                border (TerminalTiler.Border): Border configuration used by the underlying DisplayTile.
                barChar (str): Character used to draw the filled portion of the progress bar.
                barLeft (str, optional): Character or string displayed at the left edge of the bar. Defaults to "".
                barRight (str, optional): Character or string displayed at the right edge of the bar. Defaults to "".
            """
            self.max = max
            self.value = 0
            self.textLeft = "" # text on left side of progress bar
            self.textRight = "" # text on right side of progress bar
            self.textOverlay = "" # text overlayed on top of bar
            self.barChar = barChar # char used to draw bar
            self.barLeft = barLeft # left boundary of progress bar
            self.barRight = barRight # right boundary of progress bar
            self.x = x
            self.y = y
            self.width = width
            self.height = height
            self.canFocus = False
            self.visible = visible
            self.displayTile = TerminalTiler.DisplayTile(
                write_func=write_func,
                x=x,
                y=y,
                width=width,
                height=height,
                visible=visible,
                canFocus=False,
                textWrap=TerminalTiler.Style.Wrap.NOWRAP,
                textJust=TerminalTiler.Style.Justify.LJUST,
                sizeMode=TerminalTiler.Style.Size.FIXED,
                border=border,
                header=TerminalTiler.Header()
            )
            # colors
            self.colors = {
                "BORDER_FG": None,
                "BORDER_BG": None,
                "TEXT_FG": None,
                "TEXT_BG": None,
                "BORDER_FG_F": None,
                "BORDER_BG_F": None,
                "TEXT_FG_F": None,
                "TEXT_BG_F": None
            }
            self.displayTile.colors = self.colors # link objects by reference

        def drawBorder(self):
            """
            Render border.
            """
            self.displayTile.drawBorder()

        def drawText(self):
            """
            Render progress bar.
            """
            self.displayTile.drawText()

        def show(self):
            """
            Render element.
            """
            self.visible = True
            self.displayTile.show()

        def hide(self):
            """
            Hide element.
            """
            self.visible = False
            self.displayTile.hide()

        def update(self, increment:int):
            """
            Increment the progress value and redraw the progress bar.
            The current value is increased by increment and clamped to the
            configured maximum value. The bar is automatically resized to fit
            within the available tile width after accounting for any surrounding
            text and bar boundaries.

            Three text sections will be rendered if set:

                textLeft    - Rendered on left side of progress bar.
                textOverlay - Overlay text is centered within the bar and replaces the underlying bar characters.
                textRight   - Rendered on right side of progress bar.

            These sections may be formatted using the following placeholders:

                {VALUE}   - Current progress value.
                {MAX}     - Maximum progress value.
                {PERCENT} - Progress percentage (0-100).
                {RATIO}   - Progress ratio (0.0-1.0).

            Args:
                increment (int):
                    Amount to add to the current progress value.
            """
            # increment bar value
            self.value = min(self.max, self.value + increment)
            # get formatted text
            left = self.textLeft.format(VALUE=self.value, MAX=self.max, PERCENT=100*self.value/self.max, RATIO=self.value/self.max)
            right = self.textRight.format(VALUE=self.value, MAX=self.max, PERCENT=100*self.value/self.max, RATIO=self.value/self.max)
            overlay = self.textOverlay.format(VALUE=self.value, MAX=self.max, PERCENT=100*self.value/self.max, RATIO=self.value/self.max)
            # build bar 
            barWidth = max(0, self.displayTile.cols - (len(self.barLeft) + len(self.barRight) + len(left) + len(right)))
            barFilled = int(barWidth * self.value / self.max)
            barRaw = (self.barChar * barFilled)[:barFilled] + " " * (barWidth - barFilled)
            midIndex = (len(barRaw) - len(overlay)) // 2
            bar = barRaw[:midIndex] + overlay + barRaw[midIndex + len(overlay):]
            self.displayTile.update((left + self.barLeft + bar + self.barRight + right)[:self.displayTile.cols])
            self.drawText()

    class Alert:
        """
        A terminal UI region that displays a message for a set time.
        """
        def __init__(self, write_func, overlap_func, popup_lock:threading.RLock, exit_event:threading.Event, text:str, x:int, y:int, width:int, height:int, textWrap:int, textJust:int, border:"TerminalTiler.Border"):
            """
            Initialize a Alert display tile.

            The Alert will be rendered on top of all other elements.

            Args:
                write_func (callable): Function used to write output to the display.
                overlap_func (callable): Function used to query tile intersections.
                popup_lock (threading.RLock): Active alert lock.
                exit_event (threading.Event): Exit flag.
                text (str): Alert text.
                x (int): X-coordinate of the tile.
                y (int): Y-coordinate of the tile.
                width (int): Width of the tile in characters.
                height (int): Height of the tile in characters.
                textWrap (int): Text rendering mode (wrap or no-wrap).
                border (TerminalTiler.Border): Border configuration used by the underlying DisplayTile.
            """
            self.getOverlaping = overlap_func
            self.lock = popup_lock
            self.exit = exit_event
            self.close = threading.Event() # user closed alert
            self.close_key = None
            self.text = text
            self.x = x
            self.y = y
            self.width = width
            self.height = height
            self.canFocus = False
            self.visible = False
            self.waitTime = 0.5
            self.displayTile = TerminalTiler.DisplayTile(
                write_func=write_func,
                x=x,
                y=y,
                width=width,
                height=height,
                visible=False,
                canFocus=False,
                textWrap=textWrap,
                textJust=textJust,
                sizeMode=TerminalTiler.Style.Size.FIXED,
                border=border,
                header=TerminalTiler.Header()
            )
            # colors
            self.colors = {
                "BORDER_FG": None,
                "BORDER_BG": None,
                "TEXT_FG": None,
                "TEXT_BG": None,
                "BORDER_FG_F": None,
                "BORDER_BG_F": None,
                "TEXT_FG_F": None,
                "TEXT_BG_F": None
            }
            self.displayTile.colors = self.colors # link objects by reference

        def drawBorder(self):
            """
            Render border.
            """
            with self.lock:
                self.displayTile.drawBorder()

        def drawText(self):
            """
            Render Alert text.
            """
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

                remaining = duration

                while not self.exit.is_set() and not self.close.is_set():

                    # indefinite display
                    if duration < 0:
                        time.sleep(self.waitTime)
                        continue

                    # timed display
                    if remaining <= 0:
                        break

                    sleep_time = min(self.waitTime, remaining)
                    time.sleep(sleep_time)
                    remaining -= sleep_time

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
            with self.lock:
                self.visible = False
                self.displayTile.hide()

    class MessageBox:
        """
        A terminal UI region that displays a message and allows the user to select an option.
        """
        class ColorDict(dict):
            def __init__(self, owner, subkey=None, subscribers=[]):
                super().__init__()
                self.owner = owner
                self.subkey = subkey
                self.subscribers = subscribers

            def __setitem__(self, key, value):
                super().__setitem__(key, value)

                if self.subkey and key.startswith(self.subkey):
                    for d in self.subscribers:
                        d[key[len(self.subkey):]] = value

        class Button:
            """
            Button
            """
            def __init__(self, write_func, value, width:int, height:int, text:str, textWrap:int, textJust:int, border:"TerminalTiler.Border", shortcut_key:str):
                """
                Initialize a Button object.

                Args:
                    write_func (callable): Function used to write output to the display.
                    value (any): Value returned when Button is pressed.
                    width (int): Width of the tile in characters.
                    height (int): Height of the tile in characters.
                    text (str): Button text.
                    textWrap (int): Text rendering mode (wrap or no-wrap).
                    border (TerminalTiler.Border): Border configuration.
                    shortcut_key (str): TerminalTiler.Keyboard key that activates the Button.
                """
                self.write = write_func
                self.text = text
                self.shortcut_key = shortcut_key
                self.value = value
                self.displayTile = TerminalTiler.DisplayTile(
                    write_func=write_func,
                    x=0, # set at render
                    y=0, # set at render
                    width=width,
                    height=height,
                    visible=False,
                    canFocus=False,
                    textWrap=textWrap,
                    textJust=textJust,
                    sizeMode=TerminalTiler.Style.Size.FIXED,
                    border=border,
                    header=TerminalTiler.Header()
                )

        def __init__(self, write_func, overlap_func, popup_lock:threading.RLock, exit_event:threading.Event, text:str, headerText:str, x:int, y:int, width:int, height:int, textWrap:int, textJust:int, border:"TerminalTiler.Border", header:"TerminalTiler.Header"):
            """
            Initialize a MessageBox display tile.

            The MessageBox will be rendered on top of all other elements.

            Args:
                write_func (callable): Function used to write output to the display.
                overlap_func (callable): Function used to query tile intersections.
                popup_lock (threading.RLock): Active alert lock.
                exit_event (threading.Event): Exit flag.
                text (str): MessageBox text.
                headerText (str): MessageBox header text.
                x (int): X-coordinate of the tile.
                y (int): Y-coordinate of the tile.
                width (int): Width of the tile in characters.
                height (int): Height of the tile in characters.
                textWrap (int): Text rendering mode (wrap or no-wrap).
                border (TerminalTiler.Border): Border configuration used by the underlying DisplayTile.
                header (TerminalTiler.Header): Header configuration used by the underlying DisplayTile.
            """
            self.write = write_func
            self.getOverlaping = overlap_func
            self.lock = popup_lock
            self.exit = exit_event
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
                x=x,
                y=y,
                width=width,
                height=height,
                visible=False,
                canFocus=False,
                textWrap=textWrap,
                textJust=textJust,
                sizeMode=TerminalTiler.Style.Size.FIXED,
                border=border,
                header=header
            )
            # colors
            self.colors = self.ColorDict(self, "BUTTON_")
            self.colors.update({
                "BORDER_FG": None,
                "BORDER_BG": None,
                "HEADER_FG": None,
                "HEADER_BG": None,
                "TEXT_FG": None,
                "TEXT_BG": None,
                "BUTTON_BORDER_FG": None,
                "BUTTON_BORDER_BG": None,
                "BUTTON_TEXT_FG": None,
                "BUTTON_TEXT_BG": None,
                "BUTTON_BORDER_FG_F": None,
                "BUTTON_BORDER_BG_F": None,
                "BUTTON_TEXT_FG_F": None,
                "BUTTON_TEXT_BG_F": None
            })
            self.displayTile.colors = self.colors # link objects by reference

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
            total_height = 0
            row_width = 0
            row_height = 0
            row_count = 0
            rows = 0

            for rect in self.buttons:
                candidate_width = row_width + rect.displayTile.width
                candidate_count = row_count + 1

                # need candidate_count + 1 gaps (left, right, between)
                if candidate_width + candidate_count + 1 <= self.displayTile.cols:
                    row_width = candidate_width
                    row_height = max(row_height, rect.displayTile.height)
                    row_count = candidate_count
                else:
                    total_height += row_height
                    rows += 1

                    row_width = rect.displayTile.width
                    row_height = rect.displayTile.height
                    row_count = 1

            if row_count:
                total_height += row_height
                rows += 1

            if rows > 1:
                total_height += (rows - 1)

            return total_height + 2

        def addButton(self, value, width:int, height:int, text:str, textWrap:int=None, borderStyle:int=None, borderChar:str=None, shortcut_key:str=None)->Button:
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
                border=TerminalTiler.Border(
                    style=borderStyle,
                    charset=borderChar
                ),
                shortcut_key=shortcut_key
            )
            self.colors.subscribers.append(button.displayTile.colors)
            for k, v in self.colors.items():
                if k.startswith(self.colors.subkey):
                    button.displayTile.colors[k[len(self.colors.subkey):]] = v
            self.buttons.append(button)
            if self.getButtonLayoutHeight() > self.displayTile.rows:
                raise ValueError("Unable to fit all Buttons in MessageBox available space.")
            return button

        def drawBorder(self):
            """
            Render border.
            """
            with self.lock:
                self.displayTile.drawBorder()

        def drawText(self):
            """
            Render MessageBox text.
            """
            with self.lock:
                button_rows = self.getButtonLayoutHeight()
                self.displayTile.text.clear()
                self.displayTile.update(self.text + '\n' * button_rows)

        def drawButtons(self):
            rows = []
            row = []
            row_width = 0
            row_height = 0
            total_height = 0

            # build rows
            for rect in self.buttons:
                candidate_width = row_width + rect.displayTile.width
                candidate_count = len(row) + 1

                if candidate_width + candidate_count + 1 <= self.displayTile.cols:
                    row.append(rect)
                    row_width = candidate_width
                    row_height = max(row_height, rect.displayTile.height)
                else:
                    rows.append((row, row_width, row_height))
                    total_height += row_height

                    row = [rect]
                    row_width = rect.displayTile.width
                    row_height = rect.displayTile.height

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

                mid = (gap_count - 1) / 2
                order = sorted(range(gap_count), key=lambda i: (abs(i - mid), i))

                for i in range(extra):
                    gaps[order[i]] += 1

                # set button position and call drawing method
                x = gaps[0]
                for i, rect in enumerate(row):
                    rect.displayTile.x = x + self.displayTile.tx
                    rect.displayTile.y = y + self.displayTile.ty + (self.displayTile.rows - (total_height)) + 1

                    rect.displayTile.tx = rect.displayTile.x if rect.displayTile.border.style == TerminalTiler.Border.NO_BORDER else rect.displayTile.x + 1
                    rect.displayTile.ty = rect.displayTile.y if rect.displayTile.border.style == TerminalTiler.Border.NO_BORDER else rect.displayTile.y + 1

                    rect.displayTile.drawBorder()
                    rect.displayTile.text.clear()
                    rect.displayTile.update(rect.text)

                    x += rect.displayTile.width + gaps[i + 1]

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

            elif key == TerminalTiler.Keyboard.KEY_ENTER:
                if self.focusedIndex >= 0:
                    self.value = self.buttons[self.focusedIndex].value
                    self.close.set()

            else:
                for button in self.buttons:
                    if key == button.shortcut_key:
                        self.value = button.value
                        self.close.set()
                        break

        def show(self):
            """
            Render the MessageBox.
            While the MessageBox is visible, other threads are blocked from writing to the terminal.

            Returns:
                Button.value from selected Button.
            """
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
                        if self.input.is_set():
                            self.drawButtons()
                            self.input.clear()
                        time.sleep(self.waitTime)

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
            with self.lock:
                self.visible = False
                self.displayTile.hide()

    class Table:
        """
        A terminal UI region that displays a table.
        """
        class Cell:
            """
            Stores text and formatting info for a Table cell.
            """
            def __init__(self, write_func, text:str, textWrap:int, textJust:int):
                """
                Initialize a table cell.

                Args:
                    write_func (Callable):
                        Function used by the display tile to write rendered output to the
                        terminal.
                    text (str):
                        Initial text displayed in the cell.
                    textWrap (int):
                        Text wrapping mode. (WRAP or NOWRAP)
                    textJust (int):
                        Horizontal text justification. (LJUST, CENTERED, or RJUST)
                """
                self.text = text
                self.textWrap = textWrap
                self.textJust = textJust
                self.displayTile = TerminalTiler.DisplayTile(
                    write_func=write_func,
                    x=0,
                    y=0,
                    width=0,
                    height=0,
                    visible=False,
                    canFocus=False,
                    textWrap=textWrap,
                    textJust=textJust,
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
                self.text = text
                self.displayTile.text.clear()
                self.displayTile.update(text)

        class Axis:
            def __init__(self, cells:list, size:int):
                self.cells = cells
                self.size = size # width/height of row/col

        def __init__(self, write_func, x:int, y:int, width:int, height:int, visible:bool, canFocus:bool, textWrap: int, textJust: int, border:"TerminalTiler.Border", header:"TerminalTiler.Header"):
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
                x=x,
                y=y,
                width=width,
                height=height,
                visible=False,
                canFocus=canFocus,
                textWrap=TerminalTiler.Style.Wrap.NOWRAP,
                textJust=TerminalTiler.Style.Justify.LJUST,
                sizeMode=TerminalTiler.Style.Size.FIXED,
                border=border,
                header=header
            )
            self.colors = self.displayTile.colors

        def build(self):
            col_base = (self.displayTile.cols - (self.table_cols - 1)) // self.table_cols
            col_extra = (self.displayTile.cols - (self.table_cols - 1)) % self.table_cols

            row_base = (self.displayTile.rows - (self.table_rows - 1)) // self.table_rows
            row_extra = (self.displayTile.rows - (self.table_rows - 1)) % self.table_rows

            # create the cell grid
            self.cells = [[self.Cell(self.write, text="", textWrap=self.textWrap, textJust=self.textJust) for _ in range(self.table_cols)] for _ in range(self.table_rows)]

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
            self.table_cols = max([len(r) for r in data])
            self.table_rows = len(data)
            self.build()

            for r in range(self.table_rows):
                for c in range(len(data[r])):
                    self.cells[r][c].text = str(data[r][c])

        def insertRow(self, data:list, index:int=None):
            pass

        def insertCol(self, data:list, index:int=None):
            pass

        def update(self, x:int, y:int, text:str):
            self.cells[y][x].update(text)

        def drawBorder(self):
            if self.displayTile.border.style != TerminalTiler.Border.NO_BORDER:
                self.displayTile.drawBorder()

                # draw table lines and juncts
                if self.focused:
                    color_fg = self.colors.get("BORDER_FG_F", None)
                    color_bg = self.colors.get("BORDER_BG_F", None)
                else:
                    color_fg = self.colors.get("BORDER_FG", None)
                    color_bg = self.colors.get("BORDER_BG", None)

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

        def show(self):
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
                    cell.displayTile.update(cell.text)

                    x += width + 1

                y += height + 1

            self.drawBorder()

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
        self.waiting = False
        self.waitKey = None # used by waitForKey
        self.stdout_FDI = TerminalTiler.FDInterceptor(1, self.exit)
        self.keyboard = TerminalTiler.Keyboard()
        self.keyboard.subscribe(self._handleInput)
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

    def addDisplayTile(self,
        x:int, y:int, width:int, height:int,
        visible:bool=True,
        textWrap:int=None, textJust:int=None, sizeMode:int=None,
        borderStyle:int=None, borderChar:str=None,
        headerLines:int=0, headerTextWrap:int=None, headerTextJust:int=None, headerBorder:bool=False)->DisplayTile:
        """
        Creates and registers a new DisplayTile in the terminal layout.

        Performs boundary validation against the terminal size to ensure
        the tile fits within the visible viewport. Then constructs a DisplayTile
        instance with the specified border and header configuration stores it in self.tiles[].

        Args:
            x (int): DisplayTile origin column (1-based).
            y (int): DisplayTile origin row (1-based).
            width (int): DisplayTile width in characters.
            height (int): DisplayTile height in rows.
            visible (bool): Show DisplayTile?
            textWrap (int, optional): Text wrap mode. Style.Wrap.WRAP or Style.Wrap.NOWRAP.
            textJust (int, optional): Text justify mode. Style.Justify.LJUST, Style.Justify.CENTERED, or Style.Justify.RJUST.
            sizeMode (int, optional): Text buffer sizing. Style.Size.FIXED or Style.Size.SCROLLING.
            borderStyle (int, optional): Border style constant.
            borderChar (str, optional): Custom border character.
            headerLines (int): Number of header rows.
            headerTextWrap (int, optional): Header text wrap mode. Style.Wrap.WRAP or Style.Wrap.NOWRAP.
            headerTextJust (int, optional): Header text justify mode. Style.Justify.LJUST, Style.Justify.CENTERED, or Style.Justify.RJUST.
            headerBorder (bool): Draw border between header and text?

        Returns:
            DisplayTile: DisplayTile object.
        """
        #check dimensions
        if x <= 0 or x >= self.cols or y <= 0 or y >= self.rows:
            raise ValueError("DisplayTile origin is not contained by terminal")
        elif x + width - 1 > self.cols:
            raise ValueError(f"DisplayTile exceeds terminal boundary (X-axis) {x + width - 1} > {self.cols}")
        elif y + height - 1 > self.rows:
            raise ValueError(f"DisplayTile exceeds terminal boundary (Y-axis) {y + height - 1} > {self.rows}")

        tile = TerminalTiler.DisplayTile(
            write_func=self._write,
            x=x,
            y=y,
            width=width,
            height=height,
            visible=visible,
            canFocus=True,
            textWrap=textWrap,
            textJust=textJust,
            sizeMode=sizeMode,
            border=TerminalTiler.Border(
                style=borderStyle,
                charset=borderChar
            ),
            header=TerminalTiler.Header(
                lines=headerLines,
                textWrap=headerTextWrap,
                textJust=headerTextJust,
                hasBorder=headerBorder
            )
        )
        self.tiles.append(tile)
        return tile

    def addInputTile(self,
        x:int, y:int, width:int, height:int,
        visible:bool=True, canFocus:bool=True,
        prompt:str="",
        borderStyle:int=None, borderChar:str=None)->InputTile:
        """
        Creates and registers a new InputTile in the terminal layout.

        Performs boundary validation against the terminal size to ensure
        the InputTile fits within the visible viewport. Then constructs an InputTile
        instance with the specified border and header configuration stores it in self.tiles[].

        Args:
            x (int): InputTile origin column (1-based).
            y (int): InputTile origin row (1-based).
            width (int): InputTile width in characters.
            height (int): InputTile height in rows.
            visible (bool): Show InputTile?
            canFocus (bool): Can this be focused?
            prompt (str): Input prompt.
            borderStyle (int, optional): Border style constant.
            borderChar (str, optional): Custom border character.

        Returns:
            InputTile: InputTile object.
        """
        #check dimensions
        if x <= 0 or x >= self.cols or y <= 0 or y >= self.rows:
            raise ValueError("InputTile origin is not contained by terminal")
        elif x + width - 1 > self.cols:
            raise ValueError(f"InputTile exceeds terminal boundary (X-axis) {x + width - 1} > {self.cols}")
        elif y + height - 1 > self.rows:
            raise ValueError(f"InputTile exceeds terminal boundary (Y-axis) {y + height - 1} > {self.rows}")

        tile = TerminalTiler.InputTile(
            write_func=self._write,
            exit_event=self.exit,
            x=x,
            y=y,
            width=width,
            height=height,
            visible=visible,
            canFocus=canFocus,
            prompt=prompt,
            border=TerminalTiler.Border(
                style=borderStyle,
                charset=borderChar
            )
        )
        self.tiles.append(tile)
        return tile

    def addProgressBar(self,
        max:int,
        barChar:str,
        x:int, y:int, width:int,
        visible:bool=True,
        borderStyle:int=None, borderChar:str=None,
        barLeft:str="", barRight:str="")->ProgressBar:
        """
        Creates and registers a new ProgressBar in the terminal layout.

        Performs boundary validation against the terminal size to ensure
        the tile fits within the visible viewport. Then constructs a ProgressBar
        instance with the specified border configuration and stores it in self.tiles[].

        Args:
            max (int): Max value.
            barChar (str): Character(s) used to draw the progress bar.
            x (int): ProgressBar origin column (1-based).
            y (int): ProgressBar origin row (1-based).
            width (int): ProgressBar width in characters.
            visible (bool): Show ProgressBar?
            borderStyle (int, optional): Border style constant.
            borderChar (str, optional): Custom border character.
            barLeft (str, optional): Left boundary of progress bar.
            barRight (str, optional): Right boundary of progress bar.

        Returns:
            ProgressBar: ProgressBar object.
        """
        height = 1
        if borderStyle:
            if borderStyle != TerminalTiler.Border.NO_BORDER:
                height = 3
        #check dimensions
        if x <= 0 or x >= self.cols or y <= 0 or y >= self.rows:
            raise ValueError("ProgressBar origin is not contained by terminal")
        elif x + width - 1 > self.cols:
            raise ValueError(f"ProgressBar exceeds terminal boundary (X-axis) {x + width - 1} > {self.cols}")
        elif y + height - 1 > self.rows:
            raise ValueError(f"ProgressBar exceeds terminal boundary (Y-axis) {y + height - 1} > {self.rows}")
        elif max <= 0:
            raise ValueError(f"Max bar value must be > 0")

        tile = TerminalTiler.ProgressBar(
            write_func=self._write,
            max=max,
            x=x,
            y=y,
            width=width,
            height=height,
            visible=visible,
            border=TerminalTiler.Border(
                style=borderStyle,
                charset=borderChar
            ),
            barChar=barChar,
            barLeft=barLeft,
            barRight=barRight
        )
        self.tiles.append(tile)
        return tile

    def addAlert(self,
        x:int, y:int, width:int, height:int,
        text:str="", textWrap:int=None, textJust:int=None,
        borderStyle:int=None, borderChar:str=None)->Alert:
        """
        Creates and registers a new Alert in the terminal layout.

        Performs boundary validation against the terminal size to ensure
        the tile fits within the visible viewport. Then constructs an Alert
        instance with the specified border configuration and stores it in self.tiles[].

        Args:
            x (int): Alert origin column (1-based).
            y (int): Alert origin row (1-based).
            width (int): Alert width in characters.
            height (int): InputTile height in rows.
            textWrap (int, optional): Text wrap mode. Style.Wrap.WRAP or Style.Wrap.NOWRAP.
            textJust (int, optional): Text justify mode. Style.Justify.LJUST, Style.Justify.CENTERED, or Style.Justify.RJUST.
            borderStyle (int, optional): Border style constant.
            borderChar (str, optional): Custom border character.
            text (str, optional): Alert text.

        Returns:
            Alert: Alert object.
        """
        #check dimensions
        if x <= 0 or x >= self.cols or y <= 0 or y >= self.rows:
            raise ValueError("Alert origin is not contained by terminal")
        elif x + width - 1 > self.cols:
            raise ValueError(f"Alert exceeds terminal boundary (X-axis) {x + width - 1} > {self.cols}")
        elif y + height - 1 > self.rows:
            raise ValueError(f"Alert exceeds terminal boundary (Y-axis) {y + height - 1} > {self.rows}")

        tile = TerminalTiler.Alert(
            write_func=self._write,
            overlap_func=self._getIntersectingElements,
            popup_lock=self.popup,
            exit_event=self.exit,
            x=x,
            y=y,
            width=width,
            height=height,
            textWrap=textWrap,
            textJust=textJust,
            border=TerminalTiler.Border(
                style=borderStyle,
                charset=borderChar
            ),
            text=text
        )
        self.tiles.append(tile)
        return tile

    def addMessageBox(self,
        x:int, y:int, width:int, height:int,
        text:str="", textWrap:int=None, textJust:int=None,
        borderStyle:int=None, borderChar:str=None,
        headerText="", headerLines:int=0, headerTextWrap:int=None, headerTextJust:int=None, headerBorder:bool=False)->MessageBox:
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
            raise ValueError("MessageBox origin is not contained by terminal")
        elif x + width - 1 > self.cols:
            raise ValueError(f"MessageBox exceeds terminal boundary (X-axis) {x + width - 1} > {self.cols}")
        elif y + height - 1 > self.rows:
            raise ValueError(f"MessageBox exceeds terminal boundary (Y-axis) {y + height - 1} > {self.rows}")

        tile = TerminalTiler.MessageBox(
            write_func=self._write,
            overlap_func=self._getIntersectingElements,
            popup_lock=self.popup,
            exit_event=self.exit,
            text=text,
            headerText=headerText,
            x=x,
            y=y,
            width=width,
            height=height,
            textWrap=textWrap,
            textJust=textJust,
            border=TerminalTiler.Border(
                style=borderStyle,
                charset=borderChar
            ),
            header=TerminalTiler.Header(
                lines=headerLines,
                textWrap=headerTextWrap,
                textJust=headerTextJust,
                hasBorder=headerBorder
            )
        )
        self.tiles.append(tile)
        return tile

    def addTable(self,
        x:int, y:int, width:int, height:int,
        visible:bool, canFocus:bool,
        textWrap:int=None, textJust:int=None,
        borderStyle:int=None, borderChar:str=None,
        headerLines:int=0, headerTextWrap:int=None, headerTextJust:int=None, headerBorder:bool=False)->Table:
        """
        Creates and registers a new Table in the terminal layout.

        Performs boundary validation against the terminal size to ensure
        the tile fits within the visible viewport. Then constructs a Table
        instance with the specified border and header configuration stores it in self.tiles[].

        Args:
            x (int): Table origin column (1-based).
            y (int): Table origin row (1-based).
            width (int): Table width in characters.
            height (int): Table height in rows.
            visible (bool): Show Table?
            canFocus (bool): Can this be focused?
            textWrap (int, optional): Style.Wrap.WRAP or Style.Wrap.NOWRAP.
            textJust (int, optional): Style.Justify.LJUST, Style.Justify.CENTERED, or Style.Justify.RJUST.
            sizeMode (int, optional): Style.Size.FIXED or Style.Size.SCROLLING.
            borderStyle (int, optional): Border style constant.
            borderChar (str, optional): Custom border character.
            headerLines (int, optional): Number of header rows.
            headerTextWrap (int, optional): Style.Wrap.WRAP or Style.Wrap.NOWRAP.
            headerTextJust (int,  optional): Style.Justify.LJUST, Style.Justify.CENTERED, or Style.Justify.RJUST.
            headerBorder (bool, optional): Whether header has its own border.

        Returns:
            Table: Table object.
        """
        #check dimensions
        if x <= 0 or x >= self.cols or y <= 0 or y >= self.rows:
            raise ValueError("Table origin is not contained by terminal")
        elif x + width - 1 > self.cols:
            raise ValueError(f"Table exceeds terminal boundary (X-axis) {x + width - 1} > {self.cols}")
        elif y + height - 1 > self.rows:
            raise ValueError(f"Table exceeds terminal boundary (Y-axis) {y + height - 1} > {self.rows}")

        tile = TerminalTiler.Table(
            write_func=self._write,
            x=x,
            y=y,
            width=width,
            height=height,
            visible=visible,
            canFocus=canFocus,
            textWrap=textWrap,
            textJust=textJust,
            border=TerminalTiler.Border(
                style=borderStyle,
                charset=borderChar
            ),
            header=TerminalTiler.Header(
                lines=headerLines,
                textWrap=headerTextWrap,
                textJust=headerTextJust,
                hasBorder=headerBorder
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

    def _handleInput(self, key:str):
        """
        Handles keyboard input for tile navigation and scrolling.
        """
        if key == TerminalTiler.Keyboard.KEY_CTRL_C:
            self.close()

        # if alert is not active, handle input
        elif self.popup.acquire(blocking=False):
            if (key == self.waitKey or self.waitKey == TerminalTiler.Keyboard.KEY_ANY) and self.waiting:
                self.waiting = False

            elif key == TerminalTiler.Keyboard.KEY_TAB:
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

    def hideCursor(self):
        """
        Hides cursor.
        """
        self._write("\033[?25l".encode())

    def showCursor(self):
        """
        Shows cursor.
        """
        self._write("\033[?25h".encode())

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

    def waitForKey(self, key:str, waitTime:float=0.5):
        """
        Blocks current thread until the specified key is pressed.

        Args:
            key (str):
                Value stored in self.waitKey.
            waitTime (float, optional):
                Number of seconds to wait between status checks. Default: 0.5
        """
        self.waitKey = key
        self.waiting = True
        # wait
        while self.isAlive() and self.waiting:
            time.sleep(waitTime)