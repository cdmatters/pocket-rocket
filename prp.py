#!/usr/local/bin/python3
# PocketRocket - terminal hold'em in <500 lines
import asyncio
import argparse
import sys
import re
import os

ANSI_ESCAPE = re.compile(r'(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]')
if not os.path.exists(".prp"):
    os.makedirs(".prp")

COMMON_FILE = ".prp/prp_com_{}"
PRIVATE_FILE = ".prp/prp_priv_{}"

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
CARD_COLOUR = BLUE
MY_CARD_COLOUR = MAGENTA

PLAYER = None 
TOURNAMENT = None

LAST_LINE = None
NEXT_TO_PLAY = "eweezy"
START_CHIPS = 500

IS_DEALER = False

MOVE_COMMANDS = {
    "RAISE" : ["r", "raise", "raise_to"],
    "CALL" : ["c", "call"],
    "CHECK" : ["x", "check"],
    "FOLD" : ["f", "fold"],
    "ALL_IN" : ["aaa", "all-in", "allin", "all_in"],
}
LOOKUP_MOVE_COMMANDS = {shortcuts:c for c in MOVE_COMMANDS for shortcuts in MOVE_COMMANDS[c]}

COMMANDS = { 
    #TYPE: set( shortcuts )
    "HELP":[ "h","help"],
    "HISTORY":["p", "past","history" ],
    "MOVE": [s for c in MOVE_COMMANDS for s in MOVE_COMMANDS[c]], 
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
    sys.stdout.flush()

def prompt(name):
    sys.stdout.write(colour(">>>{}<<<\n".format(name), PROMPT_COLOUR))

def log_exception(e):
    clear_up_line()
    sys.stdout.write(colour(str(e), e.colour))
    sys.stdout.flush()

def write_to_file(name, string):
    # blocking
    with open(name, "a") as f:
        f.write(string)

def on_std_input():
    line = escaped(sys.stdin.readline()).lower().strip()
    if not line:
        return 

    try:
        instructions = parse_line(line)
        request = instructions["type"]
        if request == "MOVE":
            move_line = validate_command(instructions["move"])
            asyncio.ensure_future(LOOP.run_in_executor(None, write_to_file, COMMON_FILE, move_line))
            clear_up_line()
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
    except IndexError as e:
        e.colour = RED
        log_exception(e)

def parse_line(line):
    words = line.split()
    if words[0] in LOOKUP_COMMANDS: # eg "raise 100"
        return {"type": LOOKUP_COMMANDS[words[0]], "move":words[1:]}
    elif words[0][0] in LOOKUP_COMMANDS and words[0][1] in "0987654321": # eg "r100"
        return {"type": LOOKUP_COMMANDS[words[0][0]], "move":words[0]}
    else:
        raise InvalidCommandError("nope: " + line, ERROR_COLOUR)

def validate_command(move):
    if NEXT_TO_PLAY != PLAYER.name:
        raise InvalidCommandError("WAIT YOUR TURN", WARNING_COLOUR)
    if move=="lk":
        raise InvalidCommandError("invalid?: " + move, WARNING_COLOUR)
    return "line to be written to common file\n"

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

async def process_common_output(fd, tournament):
    start_request = tournament.start_request(PLAYER)
    asyncio.ensure_future(LOOP.run_in_executor(None, write_to_file, COMMON_FILE, start_request))
    print()
    async for move in read_forever(fd):
        processed_line, col = tournament.process(move)
        if processed_line:
            clear_up_line()
            print(colour(processed_line, col))
            prompt("PLAYER   to play")

async def read_forever(fd):
    while True:
        l = await asyncio.ensure_future(LOOP.run_in_executor(None, fd.readline))
        if l and l.strip():
            yield l.strip()

def highlight(move):
    if move:
        return colour(move, HISTORY_COLOUR)

class Tournament(object):
    """runs a tournament."""
    def __init__(self, is_game_owner):
        self.players = []
        self.is_game_owner = is_game_owner
        self.mid_game = False
        
    def process(self, move):
        m = move.split()
        if m[0] == "cards":
            if m[1] == PLAYER.name:
                m[2] = self.unhash(m[2])
                return " ".join(m), MY_CARD_COLOUR
            else:
                return " ".join(m), CARD_COLOUR

        elif m[0] == "add-player":
            p = Player(m[1], m[2], START_CHIPS)
            if p.name not in [pl.name for pl in self.players]:
                self.players.append(p)
                return "{p.name} joined table with {p.chips} chips.".format(p=p), WARNING_COLOUR
            else:
                return "{p.name} rejoined the table.".format(p=p), WARNING_COLOUR
        elif m[0] == "owner":
            if self.is_game_owner:
                self.process_as_owner(m[1:])
            return None, WHITE

        else:
            return move, WHITE

    def unhash(self, hashed):
        return hashed

    def start_request(self, p):
        add_player = "add-player {p.name} {p.key} {p.chips}\n".format(p=p)
        if self.is_game_owner:
            add_player += "owner start-tournament\n"
        return add_player

    def process_as_owner(self, move):
        if m[1] == "start_tournament":
            if players
        pass


class Player(object):
    def __init__(self, name, pub_key, chips):
        self.name = name
        self.key = pub_key
        self.chips = chips
        self.cards = None
    def deal(cards):
        pass

def build_parser():
    ap = argparse.ArgumentParser(description="play holdem over filesystem")
    ap.add_argument("player")
    ap.add_argument("game")
    ap.add_argument("-n", "--new-game", dest="new-game", action='store_true',)
    return ap

def check_valid_files():
    if os.path.isfile(COMMON_FILE) and args["new-game"]:
        raise argparse.ArgumentTypeError('game "{}" exists already'.format(args["game"]))
    elif not os.path.isfile(COMMON_FILE) and not args["new-game"]:
        raise argparse.ArgumentTypeError('game "{}" doesnt exist yet, use -n'.format(args["game"]))
    open(COMMON_FILE, 'a').close() #TO DO clean up this mess

if __name__=="__main__":
    args = vars(build_parser().parse_args())

    COMMON_FILE = COMMON_FILE.format(args["game"])
    PRIVATE_FILE = PRIVATE_FILE.format(args["game"])
    check_valid_files()
    
    PLAYER = Player(args["player"], "123456", START_CHIPS)
    TOURNAMENT = Tournament(args["new-game"])

    

    com_fd = open(COMMON_FILE, "r")

    LOOP.add_reader(sys.stdin.fileno(), on_std_input)
    LOOP.run_until_complete(process_common_output(com_fd, TOURNAMENT))





