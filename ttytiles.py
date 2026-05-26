import os
import sys
import threading

class TerminalTiler:
    def __init__(self):
        self.cols, self.rows = os.get_terminal_size()
        self.tiles = []

    def addTile(self, x:int, y:int, width:int, height:int, tag:str):
        self.tiles.append(Tile(x, y, width, height, tag))



class Tile:
    def __init__(self, x:int, y:int, width:int, height:int, tag:str):
        self.x = x
        self.y = y
        self.width = width 
        self.height = height 
        self.tag = tag 



class FDInterceptor:
    def __init__(self, fd, match=b"IMPORTANT"):
        self.fd = fd
        self.match = match

        self.r, w = os.pipe()

        self.real_fd = os.dup(fd)

        os.dup2(w, fd)
        os.close(w)

        if fd == 1:
            sys.stdout = os.fdopen(fd, "w", buffering=1)
        elif fd == 2:
            sys.stderr = os.fdopen(fd, "w", buffering=1)

        self.thread = threading.Thread(target=self.relay)
        self.thread.start()

    def relay(self):
        while True:
            data = os.read(self.r, 65536)

            if not data:
                break

            for line in data.splitlines(True):
                if self.match in line:
                    os.write(self.real_fd, line)

    def close(self):
        # flush python buffers
        if self.fd == 1:
            sys.stdout.flush()
        elif self.fd == 2:
            sys.stderr.flush()

        # close redirected fd -> generates EOF in pipe
        os.close(self.fd)

        # wait for relay thread to drain remaining output
        self.thread.join()