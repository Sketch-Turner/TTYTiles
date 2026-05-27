import os
import sys
import threading
from collections import deque

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
    NO_BORDER = 0
    SINGLE_BOX = 1
    DOUBLE_BOX = 2
    CUSTOM = 3
    BORDER_STYLES = {NO_BORDER, SINGLE_BOX, DOUBLE_BOX, CUSTOM}
    BORDER_CHARS = {NO_BORDER:' ', SINGLE_BOX:'┃', DOUBLE_BOX:'║'}

    def __init__(self, style: int = None, char: str = None):
        """
        Border constructor.

        Args:
            style (int): Border style.
            char (str): Custom border character. If this is not None, border.style is set to CUSTOM.
        """
        self.style = style if style in self.BORDER_STYLES else self.NO_BORDER
        if char is not None:
            self.style = self.CUSTOM
        self.char = char if char is not None else self.BORDER_CHARS.get(self.style, self.BORDER_CHARS[self.NO_BORDER])

    def getTop(self, width:int)->str:
        """
        Returns the top border line for the specified width.

        Args:
            width (int): Total width of the border line.

        Returns:
            str: Rendered top border string.
        """
        if self.style == Border.SINGLE_BOX:
            return '┏' + '━' * (width - 2) + '┓'
        elif self.style == Border.DOUBLE_BOX:
            return '╔' + '═' * (width - 2) + '╗'
        elif self.style == Border.CUSTOM:
            return self.char * width
        return ""

    def getMiddle(self, width:int):
        """
        Returns the middle separator border line for the specified width.

        Args:
            width (int): Total width of the border line.

        Returns:
            str: Rendered middle border string.
        """
        if self.style == Border.SINGLE_BOX:
            return '┣' + '━' * (width - 2) + '┫'
        elif self.style == Border.DOUBLE_BOX:
            return '╠' + '═' * (width - 2) + '╣'
        elif self.style == Border.CUSTOM:
            return self.char * width
        return ""

    def getBottom(self, width:int):
        """
        Returns the bottom border line for the specified width.

        Args:
            width (int): Total width of the border line.

        Returns:
            str: Rendered bottom border string.
        """
        if self.style == Border.SINGLE_BOX:
            return '┗' + '━' * (width - 2) + '┛'
        elif self.style == Border.DOUBLE_BOX:
            return '╚' + '═' * (width - 2) + '╝'
        elif self.style == Border.CUSTOM:
            return self.char * width
        return ""

class Tile:
    """
    A terminal UI region that renders a bordered rectangular tile
    with an optional header and scrollable/wrappable text buffer.
    """
    TEXT_NOWRAP = 0
    TEXT_WRAP = 1
    TEXT_MODES = {TEXT_NOWRAP, TEXT_WRAP}

    def __init__(self, fd:int, x:int, y:int, width:int, height:int, name:str, textMode:int, border:Border, header:Header):
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
        self.border = border
        self.header = header
        self.fd = fd

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

        self.text = deque(maxlen=self.rows)

        self.drawBorder()

    def drawBorder(self):
        """
        Draws:
            - Left and right vertical border lines
            - Top border line
            - Optional header separator (middle border)
            - Bottom border line
        """
        for row in range(self.y + 1, self.y + self.height):
            os.write(self.fd, f"\x1b[{row};{self.x}H{self.border.char}".encode())
            os.write(self.fd, f"\x1b[{row};{self.x + self.width - 1}H{self.border.char}".encode())

        os.write(self.fd, f"\x1b[{self.y};{self.x}H{self.border.getTop(self.width)}".encode())
        os.write(self.fd, f"\x1b[{self.y + self.header.rows + 1};{self.x}H{self.border.getMiddle(self.width)}".encode())
        os.write(self.fd, f"\x1b[{self.y + self.height - 1};{self.x}H{self.border.getBottom(self.width)}".encode())

    def update(self, text:str):
        """
        Appends new text to the tile's internal buffer and renders
        the visible text region in the terminal.
        """
        for line in text.split('\n'):
            if self.textMode == self.TEXT_NOWRAP:
                output = line[:self.cols]
                self.text.append(output + ' ' * (self.cols - len(output)))
            elif self.textMode == self.TEXT_WRAP:
                for i in range(0, len(line), self.cols):
                    output = line[i:i+self.cols]
                    self.text.append(output + ' ' * (self.cols - len(output)))

        row = self.ty
        for line in self.text:
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
    """TODO"""
    def __init__(self, x:int, y:int, width:int, height:int, name:str, border:Border):
        self.x = x #col
        self.y = y #row
        self.width = width 
        self.height = height 
        self.name = name 
        self.border = border

        # text
        self.rows = height
        self.cols = self.width
        self.tx = self.x
        self.ty = self.y
        if self.border.style != Border.NO_BORDER:
            self.tx += 1
            self.ty += 1
            self.rows -= 2
            self.cols -= 2

        self.prompt = ""

        self.drawBorder()


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
        self.stdout_FDI = FDInterceptor(1)

    def addTile(self, x:int, y:int, width:int, height:int, name:str, textMode:int=None, borderStyle:int=None, borderChar:str=None, headerLines:int=0, headerMode:int=None, headerBorder:bool=False):
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

        self.tiles[name] = Tile(self.stdout_FDI.real_fd, x, y, width, height, name, textMode, Border(borderStyle, borderChar), Header(headerLines, headerMode, headerBorder))

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
        maxY = max(tile.y + tile.height for tile in self.tiles.values())
        os.write(self.stdout_FDI.real_fd, f"\x1b[{maxY};{1}H".encode())

        self.show_cursor()
        self.stdout_FDI.close()