import asyncio
import sys
import re

ANSI_ESCAPE = re.compile(r'(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]')

COMMON_FILE = ".thp_com"
PRIVATE_FILE = ".thp_priv"

LOOP = asyncio.get_event_loop()

RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
DEFAULT = "\033[39m"

LAST_LINE = None

def colour(s,c):
    return "".join([c,s,DEFAULT])

def escaped(s):
    return ANSI_ESCAPE.sub('', s)

def clear_up_line():
    sys.stdout.write('\033[A')
    sys.stdout.write('\033[K')

def prompt(name):
    sys.stdout.write(">>>{}<<<\n".format(name))

def write_to_file(name, string):
    # blocking
    with open(name, "a") as f:
        f.write(string)

def on_std_input():
    line = escaped(sys.stdin.readline())

    instructions = parse_line(line)
    request = instructions["type"]

    if request == "MOVE":
        if is_valid(instructions["move"]):
            asyncio.ensure_future(LOOP.run_in_executor(None, write_to_file, COMMON_FILE, line))
            clear_up_line()
        else:
            clear_up_line()
            print(colour("WAIT YOUR TURN", RED))
    elif request == "NEXT":
        pass

def parse_line(line):
    return {"type":"MOVE", "move":"r50"}

def is_valid(move):
    return True

async def process_common_output(fd):
    async for move in read_forever(fd):
        global LAST_LINE
        LAST_LINE = move
        clear_up_line()
        print(highlight(move))
        prompt(move)

async def read_forever(fd):
    while True:
        l = await asyncio.ensure_future(LOOP.run_in_executor(None, fd.readline))
        if l:
            yield l.strip()

def highlight(move):
    if move:
        return colour(move, YELLOW)

if __name__=="__main__":
    com_fd = open(COMMON_FILE, "r")

    LOOP.add_reader(sys.stdin.fileno(), on_std_input)
    LOOP.run_until_complete(process_common_output(com_fd))




