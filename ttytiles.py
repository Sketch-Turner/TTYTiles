import os
import sys
import threading
from collections import deque

class FDInterceptor:
    def __init__(self, fd):
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
        self.default_target = func

    def close(self):
        self._running = False

        # 1. Wake up os.read() by closing WRITE side FIRST
        try:
            os.close(self.fd)  # this is the dup2'd write end
        except OSError:
            pass

        # 2. Close read end (optional, thread should already be exiting)
        try:
            os.close(self.r)
        except OSError:
            pass

        # 3. Restore original fd
        try:
            os.dup2(self.real_fd, self.fd)
            os.close(self.real_fd)
        except OSError:
            pass

        # 4. IMPORTANT: wait for thread exit
        if self.thread.is_alive():
            self.thread.join()

class Header:
    TEXT_NOWRAP = 0
    TEXT_WRAP = 1
    TEXT_MODES = {TEXT_NOWRAP, TEXT_WRAP}

    def __init__(self, lines:int=0, textMode:int=0, hasBorder:bool=False):
        self.textMode = self.textMode = textMode if textMode in self.TEXT_MODES else self.TEXT_NOWRAP
        self.hasBorder = hasBorder

        # text
        self.rows = lines
        self.text = deque(maxlen=self.rows)

class Border:
    NO_BORDER = 0
    SINGLE_BOX = 1
    DOUBLE_BOX = 2
    CUSTOM = 3
    BORDER_STYLES = {NO_BORDER, SINGLE_BOX, DOUBLE_BOX, CUSTOM}
    BORDER_CHARS = {NO_BORDER:' ', SINGLE_BOX:'┃', DOUBLE_BOX:'║'}

    def __init__(self, style: int = None, char: str = None):
        self.style = style if style in self.BORDER_STYLES else self.NO_BORDER
        if char is not None:
            self.style = self.CUSTOM
        self.char = char if char is not None else self.BORDER_CHARS.get(self.style, self.BORDER_CHARS[self.NO_BORDER])

    def getTop(self, width:int)->str:
        if self.style == Border.SINGLE_BOX:
            return '┏' + '━' * (width - 2) + '┓'
        elif self.style == Border.DOUBLE_BOX:
            return '╔' + '═' * (width - 2) + '╗'
        elif self.style == Border.CUSTOM:
            return self.char * width
        return ""

    def getMiddle(self, width:int):
        if self.style == Border.SINGLE_BOX:
            return '┣' + '━' * (width - 2) + '┫'
        elif self.style == Border.DOUBLE_BOX:
            return '╠' + '═' * (width - 2) + '╣'
        elif self.style == Border.CUSTOM:
            return self.char * width
        return ""

    def getBottom(self, width:int):
        if self.style == Border.SINGLE_BOX:
            return '┗' + '━' * (width - 2) + '┛'
        elif self.style == Border.DOUBLE_BOX:
            return '╚' + '═' * (width - 2) + '╝'
        elif self.style == Border.CUSTOM:
            return self.char * width
        return ""

class Tile:
    TEXT_NOWRAP = 0
    TEXT_WRAP = 1
    TEXT_MODES = {TEXT_NOWRAP, TEXT_WRAP}

    def __init__(self, fd:int, x:int, y:int, width:int, height:int, name:str, textMode:int, border:Border, header:Header):
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
        for row in range(self.y + 1, self.y + self.height):
            os.write(self.fd, f"\x1b[{row};{self.x}H{self.border.char}".encode())
            os.write(self.fd, f"\x1b[{row};{self.x + self.width - 1}H{self.border.char}".encode())

        os.write(self.fd, f"\x1b[{self.y};{self.x}H{self.border.getTop(self.width)}".encode())
        os.write(self.fd, f"\x1b[{self.y + self.header.rows + 1};{self.x}H{self.border.getMiddle(self.width)}".encode())
        os.write(self.fd, f"\x1b[{self.y + self.height - 1};{self.x}H{self.border.getBottom(self.width)}".encode())

    def update(self, text:str):
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
    def __init__(self):
        if os.name == "nt":
            os.system("chcp 65001 > nul") #switch to unicode charset
        self.cols, self.rows = os.get_terminal_size()
        self.tiles = {}
        self.stdout_FDI = FDInterceptor(1)

    def addTile(self, x:int, y:int, width:int, height:int, name:str, textMode:int=None, borderStyle:int=None, borderChar:str=None, headerLines:int=0, headerMode:int=None, headerBorder:bool=False):
        #check dimensions
        if x <= 0 or x >= self.cols or y <= 0 or y >= self.rows:
            raise ValueError("Tile origin is not contained by terminal")
        elif x + width >= self.cols:
            raise ValueError("Tile exceeds terminal boundary (X-axis)")
        elif y + height >= self.rows:
            raise ValueError("Tile exceeds terminal boundary (Y-axis)")

        self.tiles[name] = Tile(self.stdout_FDI.real_fd, x, y, width, height, name, textMode, Border(borderStyle, borderChar), Header(headerLines, headerMode, headerBorder))

    def clearScreen(self):
        os.write(self.stdout_FDI.real_fd, "\x1b[2J".encode())

    def hide_cursor(self):
        os.write(self.stdout_FDI.real_fd, "\033[?25l".encode())

    def show_cursor(self):
        os.write(self.stdout_FDI.real_fd, "\033[?25h".encode())

    def close(self):
        maxY = max(tile.y + tile.height for tile in self.tiles.values())
        os.write(self.stdout_FDI.real_fd, f"\x1b[{maxY};{1}H".encode())

        self.show_cursor()
        self.stdout_FDI.close()