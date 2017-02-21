#!/usr/local/bin/python3
# PocketRocket - terminal hold'em in <500 lines
import asyncio
import argparse
import sys
import itertools
import random
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
NEXT_TO_PLAY = ""
START_CHIPS = 500

IS_DEALER = False

MOVE_COMMANDS = {
    "RAISE" : ["r", "raise", "raise_to"],
    "CALL" : ["c", "call"],
    "CHECK" : ["x", "check"],
    "FOLD" : ["f", "fold"],
    "ALL_IN" : ["aaa", "all-in", "allin", "all_in"],
    "DEAL": ["d", "deal"]
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
    sys.stdout.flush()

def log_exception(e):
    clear_up_line()
    sys.stdout.write(colour(str(e), e.colour))
    sys.stdout.flush()

def write_to_file(file, string):
    # blocking
    with open(file, "a") as f:
        f.write(string)

def async_write(string):
    asyncio.ensure_future(LOOP.run_in_executor(None, write_to_file, COMMON_FILE, string))
    
def on_std_input():
    line = escaped(sys.stdin.readline()).lower().strip()
    if not line:
        return 

    try:
        instructions = parse_line(line)
        request = instructions["type"]
        if request == "MOVE":
            move_line = validate_move(instructions["move"])
            async_write(move_line)
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
    # yield from asyncio.sleep(0.3)

def parse_line(line):
    words = line.split()
    if words[0] in LOOKUP_COMMANDS: # eg "raise 100"
        return {"type": LOOKUP_COMMANDS[words[0]], "move":words,}
    elif words[0][0] in LOOKUP_COMMANDS and words[0][1] in "0987654321": # eg "r100"
        return {"type": LOOKUP_COMMANDS[words[0][0]], "move":[words[0][0], words[0][1]]}
    else:
        raise InvalidCommandError("nope: {}\n".format(line), ERROR_COLOUR)

def validate_move(move):
    if LOOKUP_MOVE_COMMANDS[move[0]]=="DEAL":
        if TOURNAMENT.start_game and TOURNAMENT.is_owner:
            TOURNAMENT.start_game = False
            return TOURNAMENT.deal_hands_request()
        else :
            InvalidCommandError("you cant do this now\n", WARNING_COLOUR)
    elif NEXT_TO_PLAY != PLAYER.name:
        raise InvalidCommandError("WAIT YOUR TURN\n", WARNING_COLOUR)
    elif LOOKUP_MOVE_COMMANDS[move[0]]=="RAISE":
        return "move {name} raises {value}"
    elif LOOKUP_MOVE_COMMANDS[move[0]]=="CALL":
        return "move {name} call {value}"
    elif LOOKUP_MOVE_COMMANDS[move[0]]=="CHECK":
        return "move {name} checks".format(name=PLAYER.name)
    elif LOOKUP_MOVE_COMMANDS[move[0]]=="FOLD":
        return "move {name} folds".format(name=PLAYER.name)
    elif LOOKUP_MOVE_COMMANDS[move[0]]=="ALL_IN":
        return "move {name} is all in with {value}"
    else:
        raise InvalidCommandError("invalid?: {}\n".format(move), WARNING_COLOUR)

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

async def process_common_output(read_fd, tournament):
    start_request = tournament.start_request(PLAYER)
    async_write(start_request)    
    print()
    async for move in read_forever(read_fd):
        processed_line, col = tournament.process(move)
        clear_up_line()
        if processed_line:
            print(colour(processed_line, col))
        prompt(tournament.prompt)



async def read_forever(fd):
    while True:
        l = await asyncio.ensure_future(LOOP.run_in_executor(None, fd.readline))
        if l and l.strip():
            yield l.strip()

class Tournament(object):
    """runs a tournament."""
    def __init__(self, is_owner):
        self.players = []
        self.is_owner = is_owner
        self.start_game = False
        self.current_game = None
        self.current_players = []
        self.prompt = "waiting for players" if is_owner else "waiting for dealer"
        
    def process(self, move):
        global NEXT_TO_PLAY

        m = move.split()
        processed_move = ("", WHITE)
        
        if m[0] == "hands":
            if m[1] == PLAYER.name:
                m[3] = PLAYER.unhash(m[3])
                processed_move = (" ".join(m), MY_CARD_COLOUR)
            else:
                processed_move = (" ".join(m), CARD_COLOUR)

            self.start_game = False
            player = next((p for p in self.players if p.name == m[1]),None)
            self.current_players.append(player)

        elif m[0] == "add-player":
            p = Player(m[1], m[2], START_CHIPS)
            if p.name not in [pl.name for pl in self.players]:
                self.players.append(p)
                processed_move =  ("{p.name} joined table with {p.chips} chips.".format(p=p), WARNING_COLOUR)
            else:
                processed_move =  ("{p.name} rejoined the table.".format(p=p), WARNING_COLOUR)
        
        elif m[0] == "owner":
            if self.is_owner:
                processed_move =  self.process_as_owner(m[1:])
            else: 
                processed_move =  (None, WHITE)
        
        elif m[0] == "play_request":
            NEXT_TO_PLAY = m[1]
            self.prompt = "waiting for {}".format(NEXT_TO_PLAY)
            processed_move = (None, WHITE)

        elif m[0] == "move":
            processed_move = " ".join(m[1:]), WHITE
            if self.is_owner:
                self.current_game.advance_player()
                async_write(self.play_request(self.current_game.next_to_play()))


        elif m[0] == "show_cards":
            pass

        elif m[0] == "chat":
            pass 

        else:
            processed_move =  (move, WHITE)

        if self.start_game and len(self.players) > 1:
            self.prompt = "ready? type D to deal."

            
        
        return processed_move

    def start_request(self, p):
        add_player = "add-player {p.name} {p.key} {p.chips}\n".format(p=p)
        if self.is_owner:
            add_player += "master {p.name} is owner\nowner start-game\n".format(p=p)
        return add_player

    def deal_hands_request(self):
        return "owner deal-hands\n"

    def play_request(self, name):
        return "play_request {}\n".format(name)

    def process_as_owner(self, moves):
        if moves[0] == "start-game":
            self.start_game = True
            return (None, WHITE)
        if moves[0] == "deal-hands":
            self.current_game = Game([p for p in self.players if p.active_in_tournament], self.is_owner, 0)
            for c in self.current_game.players:
                c.active_in_game = True
            self.current_game.deal_hands()
            self.prompt = "waiting for {}".format(self.current_game.next_to_play())
            async_write(self.play_request(self.current_game.next_to_play()))
        return (None, WHITE)



class Game(object):
    def __init__(self, players, is_owner, dealer):
        self.players = players
        self.is_owner = is_owner
        self.deck = Deck() if is_owner else None
        self.cards = None
        self.dealer = dealer
        self.to_play = dealer + 3

        self.deal_hand_message = "hands {name} -> {cards}\n"
        self.deal_cards_message = "cards {cards}\n"
 
    def next_to_play(self):
        return self.players[self.to_play%len(self.players)].name
        # if not owner to play
    def advance_player(self):
        self.to_play += 1
        
    def deal_hands(self):
        for p in self.players:
            cards  = self.deck.deal(2)
            async_write(self.deal_hand_message.format(name=p.name, cards=p.hash("-".join(cards))))
        pass

class Deck(object):
    suits = "CDHS"
    ranks = "23456789TJQKA"
    def __init__(self):
        self.whole_deck = [ a+b for a,b in itertools.product(Deck.ranks,Deck.suits)]
        self.dealt = []
    def deal(self, n):
        c = random.sample(self.whole_deck, n)
        self.dealt.extend(c)
        [self.whole_deck.remove(dead) for dead in c]
        return c

class Player(object):
    def __init__(self, name, pub_key, chips):
        self.name = name
        self.key = pub_key
        self.chips = chips
        self.cards = None
        self.active_in_game = False
        self.active_in_tournament = True
    def deal(cards):
        pass
    def unhash(self, hashed):
        return  "".join(hashed[7:-8])
    def hash(self, to_hash):
        return "ad342sf"+to_hash+"lkdhsr34"

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

if __name__=="__main__":
    args = vars(build_parser().parse_args())

    COMMON_FILE = COMMON_FILE.format(args["game"])
    PRIVATE_FILE = PRIVATE_FILE.format(args["game"])
    # check_valid_files()

    # is this bad? probably...
    write_fd = open(COMMON_FILE, "a")
    read_fd = open(COMMON_FILE, "r")
    
    PLAYER = Player(args["player"], "123456", START_CHIPS)
    TOURNAMENT = Tournament(args["new-game"])

    LOOP.add_reader(sys.stdin.fileno(), on_std_input) #heavy?
    LOOP.run_until_complete(process_common_output(read_fd, TOURNAMENT))

    write_fd.close()
    read_fd.close()





