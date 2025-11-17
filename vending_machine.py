#
# STUDENT version for Project 1 to be used on the Pi500.
# TPRG2131 Fall 202x
# Updated Phil J (Fall 202x) for user with the FreeSimpleGUI lib
# 
# Kyle Krepelka
# 100923825
# Nov 17, 2025
#
# Oct 4, 2021 - initial version
# Nov 17, 2022 - Updated for Fall 2022.
# 

# PySimpleGUI recipes used:
#
# Persistent GUI example
# https://pysimplegui.readthedocs.io/en/latest/cookbook/#recipe-pattern-2a-persistent-window-multiple-reads-using-an-event-loop
#
# Asynchronous Window With Periodic Update
# https://pysimplegui.readthedocs.io/en/latest/cookbook/#asynchronous-window-with-periodic-update

import FreeSimpleGUI as sg
from time import sleep

# Hardware interface module
# Checks if on Raspberry Pi, if not program runs in GUI only mode
hardware_present = False
try:
    hardware_present = True
    from gpiozero.pins.pigpio import PiGPIOFactory
    from gpiozero import Button, Servo
except ModuleNotFoundError:
    print("Not on a Raspberry Pi or gpiozero not installed.")

# Testing flag
TESTING = True

def log(s):
    """Print debugging messages when TESTING=True."""
    if TESTING:
        print(s)

def gui_log(window, message):
    """Send output text into the GUI Multiline display."""
    window["-OUTPUT-"].update(message + "\n", append=True)


#   VENDING MACHINE CLASS
class VendingMachine(object):
    """Main vending machine controller. Handles coins, states, products, and servo."""

    PRODUCTS = {
        "suprise": ("SURPRISE", 150),
        "pop": ("POP", 125),
        "chips": ("CHIPS", 200),
        "chocolate": ("CHOCOLATE", 175),
        "beer": ("BEER", 250)
    }

    COINS = {
        "5": ("5¢", 5),
        "10": ("10¢", 10),
        "25": ("25¢", 25),
        "100": ("$1", 100),
        "200": ("$2", 200)
    }

    def __init__(self):
        self.state = None	# Current state (e.g, waiting)
        self.states = {}	
        self.event = ""		# Event from GUI (coin,product,return)
        self.amount = 0		# Total amount inserted
        self.change_due = 0	
        self.window = None

        # Build sorted coin values list
        self.coin_values = sorted([v[1] for v in self.COINS.values()], reverse=True)

        # Servo on GPIO17
        if hardware_present:
            self.servo = Servo(17)
        else:
            self.servo = None
    
    # State machine utilities
    def add_state(self, state):
        self.states[state.name] = state

    def go_to_state(self, state_name):
        if self.state:
            log(f"Exiting {self.state.name}")
            self.state.on_exit(self)

        self.state = self.states[state_name]
        log(f"Entering {self.state.name}")
        self.state.on_entry(self)

    def update(self):
        if self.state:
            self.state.update(self)

    def add_coin(self, coin_key):
        """Add a coin to the current amount."""
        self.amount += self.COINS[coin_key][1]

    def dispense_servo(self):
        """Move servo 3 times to simulate vending."""
        if self.servo:
            for _ in range(3):
                self.servo.mid(); sleep(0.3)
                self.servo.max(); sleep(0.3)
                self.servo.min(); sleep(0.3)

    def button_action(self):
        """Hardware GPIO RETURN button callback."""
        self.event = "RETURN"
        self.update()


#   STATE CLASSES
class State(object):
    """Base state class."""
    _NAME = ""
    @property
    def name(self): return self._NAME
    def on_entry(self, machine): pass
    def on_exit(self, machine): pass
    def update(self, machine): pass

# 	WAITING STATE - waiting for first coin
class WaitingState(State):
    _NAME = "waiting"
    def update(self, machine):
        if machine.event in machine.COINS:
            machine.add_coin(machine.event)
            gui_log(machine.window, f"Coin inserted: {machine.COINS[machine.event][0]}")
            machine.go_to_state("add_coins")

#	ADD COINS STATE - accepts coins or product selection
class AddCoinsState(State):
    _NAME = "add_coins"
    def update(self, machine):

        # RETURN pressed, program cancels and returns money
        if machine.event == "RETURN":
            gui_log(machine.window, f"Returning all coins: ${machine.amount/100:.2f}")
            machine.change_due = machine.amount
            machine.amount = 0
            machine.go_to_state("count_change")
        
        # Another coin is inserted
        if machine.event in machine.COINS:
            machine.add_coin(machine.event)
            gui_log(machine.window, f"Coin inserted: {machine.COINS[machine.event][0]}")
            return
        
        # Product selected
        if machine.event in machine.PRODUCTS:
            name, cost = machine.PRODUCTS[machine.event]

            if machine.amount >= cost:
                gui_log(machine.window, f"Selected: {name}")
                machine.go_to_state("deliver_product")
            else:
                needed = cost - machine.amount
                gui_log(machine.window, f"Need ${needed/100:.2f} more for {name}")

#  DELIVER PRODUCT STATE - servo movement and change calc
class DeliverProductState(State):
    _NAME = "deliver_product"

    def on_entry(self, machine):
        name, cost = machine.PRODUCTS[machine.event]
        machine.change_due = machine.amount - cost  # compute change after purchase
        machine.amount = 0

        gui_log(machine.window, f"Dispensing: {name}...")
        machine.dispense_servo()

        if machine.change_due > 0:
            machine.go_to_state("count_change")
        else:
            gui_log(machine.window, "Thank you! No change.")
            machine.go_to_state("waiting")

# COUNT CHANGE STATE - returns change 
class CountChangeState(State):
    _NAME = "count_change"

    def on_entry(self, machine):
        gui_log(machine.window, f"Change due: ${machine.change_due/100:.2f}")

    def update(self, machine):
        for coin in machine.coin_values:
            while machine.change_due >= coin:
                gui_log(machine.window, f"Returning {coin}¢")
                machine.change_due -= coin
        # When no change left return to idle
        if machine.change_due == 0:
            gui_log(machine.window, "Transaction complete. Returning to idle.")
            machine.go_to_state("waiting")



#   MAIN GUI PROGRAM

if __name__ == "__main__":

    sg.theme("BluePurple")

    # Coin buttons
    coin_col = [[sg.Text("ENTER COINS", font=("Helvetica", 24))]]
    for key in VendingMachine.COINS:
        label = VendingMachine.COINS[key][0]
        coin_col.append([sg.Button(label, key=key, font=("Helvetica", 18))])

    # Product buttons + PRICE beside them  (MATCHES YOUR PHOTO)
    prod_col = [[sg.Text("SELECT ITEM", font=("Helvetica", 24))]]
    for key in VendingMachine.PRODUCTS:
        item_name, price = VendingMachine.PRODUCTS[key]
        price_str = f"${price/100:.2f}"

        prod_col.append([
            sg.Button(key, font=("Helvetica", 18), size=(10,1)),
            sg.Text(price_str, font=("Helvetica", 18), pad=((20,0),(5,5)))
        ])

    # GUI Output console
    layout = [
        [sg.Column(coin_col), sg.VSeparator(), sg.Column(prod_col)],
        [sg.Button("RETURN", font=("Helvetica", 14))],
        [sg.Multiline(key="-OUTPUT-", autoscroll=True, size=(60,10), disabled=True)]
    ]

    window = sg.Window("Vending Machine", layout)	# Intializes vending machine object and states

    vending = VendingMachine()
    vending.window = window

    # Add states
    vending.add_state(WaitingState())
    vending.add_state(AddCoinsState())
    vending.add_state(DeliverProductState())
    vending.add_state(CountChangeState())
    vending.go_to_state("waiting")			  # Starts in waiting state

    # Hardware button on GPIO5
    if hardware_present:
        try:
            key1 = Button(5, pull_up=True)
            key1.when_pressed = vending.button_action
            print("GPIO RETURN button enabled.")
        except:
            print("GPIO failed to initialize.")

    # Main event loop
    while True:
        event, values = window.read(timeout=10)
        if event in (sg.WIN_CLOSED, "Exit"):	# Closes window and ends program
            break

        vending.event = event		# Sets current event for state machine
        vending.update()			# Runs state logic

    window.close()
    print("Normal exit")