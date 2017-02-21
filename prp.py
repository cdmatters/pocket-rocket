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
START_CHIPS = 500

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

####### -------- AUX METHODS --------- ######
### ------------------------------------- ###

def colour(s,c):
    return "".join([c,s,DEFAULT])

def escaped(s):
    return ANSI_ESCAPE.sub('', s)

def clear_up_line(n):
    for _ in range(n):
        sys.stdout.write('\033[A')
        sys.stdout.write('\033[K')
        sys.stdout.flush()

def prompt(p_list):
    p_list[0] = ">>>  " + p_list[0]
    p_list[-1] = p_list[-1] + "  <<<"

    print(colour(" <<<\n>>>  ".join(p_list), PROMPT_COLOUR))

def log_exception(e):
    clear_up_line(1)
    print(colour(str(e), e.colour))

def write_to_file(file, string):
    # blocking
    with open(file, "a") as f:
        f.write(string)
        f.write("\n")

def async_write(string):
    asyncio.ensure_future(LOOP.run_in_executor(None, write_to_file, COMMON_FILE, string))

async def read_forever(fd):
    while True:
        l = await asyncio.ensure_future(LOOP.run_in_executor(None, fd.readline))
        if l and l.strip():
            yield l.strip()

class InvalidCommandError(Exception):
    '''This command is not recognised'''
    def __init__(self, message, colour=ERROR_COLOUR):
        super(InvalidCommandError, self).__init__(message)
        self.colour = colour

####### ---------- PLAYER INPUT ------------- ######
### -------------------------------------------- ###

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
            clear_up_line(1)
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
    except (IndexError, ValueError )as e:
        e.colour = RED
        log_exception(e)


def parse_line(line):
    words = line.split()
    if words[0] in LOOKUP_COMMANDS: # eg "raise 100"
        return {"type": LOOKUP_COMMANDS[words[0]], "move":words,}
    elif words[0][0] in LOOKUP_COMMANDS and words[0][1] in "0987654321": # eg "r100"
        return {"type": LOOKUP_COMMANDS[words[0][0]], "move":[words[0][0], int(words[0][1:])]}
    else:
        raise InvalidCommandError("nope: {}".format(line), ERROR_COLOUR)

def validate_move(move):
    this_move = LOOKUP_MOVE_COMMANDS[move[0]]
    if this_move == "DEAL":
        if TOURNAMENT.ready_to_deal and TOURNAMENT.is_owner:
            # should lock on a few things here: current game != None, 2 players etc
            TOURNAMENT.ready_to_deal = False
            return TOURNAMENT.deal_hands()
        else:
            raise InvalidCommandError("you cant do this now", WARNING_COLOUR)
    elif TOURNAMENT.next_to_play() != PLAYER.name:
        raise InvalidCommandError("WAIT YOUR TURN", WARNING_COLOUR)
    elif this_move == "RAISE":
        return "move {name} raises {value}".format(name=PLAYER.name, value=move[1])
    elif this_move == "CALL":
        return "move {name} call {value}".format(name=PLAYER.name, value=move[1])
    elif this_move == "CHECK":
        return "move {name} checks".format(name=PLAYER.name)
    elif this_move == "FOLD":
        return "move {name} folds".format(name=PLAYER.name)
    elif this_move == "ALL_IN":
        return "move {name} is all in with {value}".format(name=PLAYER.name, value=move[1])
    else:
        raise InvalidCommandError("invalid?: {}".format(move), WARNING_COLOUR)

def print_help():
    help_string = "\n".join([ c + " -> " + "|".join(COMMANDS[c]) for c in COMMANDS])
    clear_up_line(1)
    print(colour(help_string, HELP_COLOUR))

def print_status():
    pass

def print_history():
    pass

def print_chips():
    pass

####### ---------- PLAYER OUTPUT ------------- ######
### --------------------------------------------- ###

async def process_common_output(read_fd, tournament):
    add_player_request = tournament.add_player_request(PLAYER)
    async_write(add_player_request)    
    print()
    async for move in read_forever(read_fd):
        processed_line, col = tournament.process(move)
        clear_up_line(len(tournament.prompt))
        
        if processed_line:
            print(colour(processed_line, col))
        
        prompt(tournament.prompt)

class Tournament(object):
    """runs a tournament."""
    def __init__(self, is_owner):
        self.players = []
        self.is_owner = is_owner
        self.ready_to_deal = True
        self.current_game = None
        self.current_players = []
        self.prompt = ["waiting for players"] if is_owner else ["waiting for dealer"]
        self.dealer = 0 #me 


    def process_hands(self, name, card_hash):
        hand_string = "{name} -> {cards}"
        self.ready_to_deal = False
        if name == PLAYER.name:
            unhashed = PLAYER.unhash(card_hash)
            self.current_game.my_cards = unhashed
            hs = hand_string.format(name=name, cards=unhashed)
            return hs, MY_CARD_COLOUR
        else:
            hs = hand_string.format(name=name, cards=card_hash)
            return  hs, CARD_COLOUR

    def process_add_player(self, name, key, start_chips):
        p = Player(name, key, start_chips)
        if p.name not in [pl.name for pl in self.players]:
            self.players.append(p)
            async_write(self.start_game_request(0)) # eek not threadsafe
            return "{p.name} joined table with {p.chips} chips.".format(p=p), WARNING_COLOUR
        else:
            return "{p.name} rejoined the table.".format(p=p), WARNING_COLOUR

    def process_move(self, moves):
        self.current_game.advance_player()
        return " ".join(moves), WHITE

    def process(self, move):
        m = move.split()
        processed_move = ("", WHITE)
        
        if m[0] == "hands":
            processed_move = self.process_hands(m[1], m[3])
        elif m[0] == "add-player":
            processed_move = self.process_add_player(m[1], m[2], START_CHIPS)
        elif m[0] == "owner":
            processed_move = self.process_as_owner(m[1:]) if self.is_owner else (None, WHITE)
        elif m[0] == "new_game":
            if self.ready_to_deal:
                active_players = [p for p in self.players if p.active_in_tournament]
                self.current_game = Game(active_players, self.is_owner, int(m[1]))
        elif m[0] == "move":
            processed_move = self.process_move(m[1:])
        elif m[0] == "show_cards":
            pass
        elif m[0] == "chat":
            pass 
        else:
            processed_move =  (move, WHITE)
        
        self.set_prompt()
        
        return processed_move

    def set_prompt(self):
        owner_to_deal = self.is_owner and self.ready_to_deal and self.current_game 
        mid_game = (not self.ready_to_deal) and self.current_game
        
        if owner_to_deal and len(self.current_game.players) > 1:
            self.prompt = ["ready to start? type D to deal."]
        elif mid_game:
            sc = self.current_game.shared_cards[:]
            sc.extend(["++"]*(5-len(sc)))
            hud = {
                "cards": self.current_game.my_cards,
                "deck": "-".join(sc),
                "pot": 3750,
                "chips": 5000,
                "last_raise": 450
            }
            self.prompt =[ 
                "waiting for {}".format(self.next_to_play()), 
                "{cards} : {deck} : P{pot}: C{chips}: L{last_raise}".format(**hud)]


    def process_as_owner(self, moves):
        
        return (None, WHITE)

    def deal_hands(self):
        return self.current_game.deal_hands()

    def add_player_request(self, p):
        return  "add-player {p.name} {p.key} {p.chips}".format(p=p)

    def start_game_request(self, dealer):
        return "new_game {dealer}".format(dealer=dealer)

    def next_to_play(self):
        if self.current_game:
            return self.current_game.next_to_play()
        else:
            return "dealer"

####### ---------- MINOR CLASSES ------------- ######
### --------------------------------------------- ###

class Game(object):
    def __init__(self, players, is_owner, dealer):
        self.players = players
        self.is_owner = is_owner
        self.deck = Deck() if is_owner else None
        self.my_cards = None
        self.shared_cards = ["AC", "JS", "2D"]
        self.dealer = dealer
        self.to_play = dealer + 3

        self.deal_hand_message = "hands {name} -> {cards}"
        self.deal_cards_message = "cards {cards}"

        for c in self.players:
            c.active_in_game = True
 
    def next_to_play(self):
        return self.players[self.to_play%len(self.players)].name
        # if not owner to play
    def advance_player(self):
        self.to_play += 1

    def deal_hands(self):
        for p in self.players:
            cards  = self.deck.deal(2)
            async_write(self.deal_hand_message.format(name=p.name, cards=p.hash("-".join(cards))))

    def process_move(self, move):
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





