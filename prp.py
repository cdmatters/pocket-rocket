#!/usr/local/bin/python3
import asyncio
import argparse
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

ERROR_COLOUR = RED
WARNING_COLOUR = YELLOW
HELP_COLOUR = CYAN
PROMPT_COLOUR = WHITE
HISTORY_COLOUR = GREEN

LAST_LINE = None

COMMANDS = { 
    #TYPE: set( shortcuts )
    "HELP":[ "h","help"],
    "HISTORY":["p", "past","history" ],
    "MOVE": ["r", "raise", "c", "call", "f", "fold", "_", "check", "A", "all_in", "allin", "all-in"], 
    "CHIPS": ["£","$","chips", "money", "chip", "cash" ],
    "STATUS": ["?","s", "status", "stat" ]
}

LOOKUP_COMMANDS = {shortcuts:c for c in COMMANDS for shortcuts in COMMANDS[c]}

class InvalidCommandError(Exception):
    '''This command is not recognised'''
    def __init__(self, message, colour=ERROR_COLOUR):
        super(InvalidCommandError, self).__init__(message)
        self.colour = colour

def colour(s,c):
    return "".join([c,s,DEFAULT])

def escaped(s):
    return ANSI_ESCAPE.sub('', s)

def clear_up_line():
    sys.stdout.write('\033[A')
    sys.stdout.write('\033[K')

def prompt(name):
    sys.stdout.write(colour(">>>{}<<<\n".format(name), PROMPT_COLOUR))

def log_exception(e):
    clear_up_line()
    sys.stdout.write(colour(str(e), e.colour))

def write_to_file(name, string):
    # blocking
    with open(name, "a") as f:
        f.write(string)

def on_std_input():
    line = escaped(sys.stdin.readline()).lower()

    try:
        instructions = parse_line(line)
        request = instructions["type"]
        if request == "MOVE":
            if is_valid(instructions["move"]):
                asyncio.ensure_future(LOOP.run_in_executor(None, write_to_file, COMMON_FILE, line))
                clear_up_line()
            else:
                raise InvalidCommandError("invalid?: " + line, WARNING_COLOUR)
        elif request == "STATUS":
            print_status()
        elif request == "HELP":
            print_help()
        elif request == "HISTORY":
            print_history()
        elif request == "CHIPS":
            print_history()
    except InvalidCommandError as e:
        log_exception(e)


def parse_line(line):

    words = line.split()
    if words[0] in LOOKUP_COMMANDS: # eg "raise 100"
        return {"type": LOOKUP_COMMANDS[words[0]], "move":words}
    elif words[0][0] in LOOKUP_COMMANDS and words[0][1] in "0987654321": # eg "r100"
        return {"type": LOOKUP_COMMANDS[words[0][0]], "move":words}
    else:
        raise InvalidCommandError("nope: " + line, ERROR_COLOUR)

def is_valid(move):
    return True

def print_help():
    help_string = "\n".join([ c + " -> " + "|".join(COMMANDS[c]) for c in COMMANDS])
    clear_up_line()
    print(colour(help_string, HELP_COLOUR))

def print_status():
    pass

def print_history():
    pass

def print_chips():
    pass

async def process_common_output(fd):
    async for move in read_forever(fd):
        global LAST_LINE
        LAST_LINE = move
        clear_up_line()
        print(highlight(move))
        prompt("PLAYER to play")

async def read_forever(fd):
    while True:
        l = await asyncio.ensure_future(LOOP.run_in_executor(None, fd.readline))
        if l:
            yield l.strip()

def highlight(move):
    if move:
        return colour(move, HISTORY_COLOUR)

if __name__=="__main__":

    com_fd = open(COMMON_FILE, "r")

    LOOP.add_reader(sys.stdin.fileno(), on_std_input)
    LOOP.run_until_complete(process_common_output(com_fd))




