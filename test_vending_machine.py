"""
PyTest for  testing vending_machine.py
Ensures state transitions, coin totals, product dispensing,
and change-return logic all function correctly.
"""

import pytest
from vending_machine import (
    VendingMachine,
    WaitingState,
    AddCoinsState,
    DeliverProductState,
    CountChangeState
)



# FIXTURE — creates a fully-initialized machine for each test
@pytest.fixture
def machine():
    vm = VendingMachine()
    vm.add_state(WaitingState())
    vm.add_state(AddCoinsState())
    vm.add_state(DeliverProductState())
    vm.add_state(CountChangeState())
    vm.go_to_state("waiting")

    # Mock servo so tests run without Raspberry Pi hardware
    vm.dispense_servo = lambda: None

    return vm


# TEST 1 — Initial State
def test_initial_state(machine):
    assert machine.state.name == "waiting"
    assert machine.amount == 0
    assert machine.change_due == 0


# TEST 2 — Verify all product prices are correct
def test_product_prices():
    expected_prices = {
        "suprise": 150,
        "pop": 125,
        "chips": 200,
        "choc": 175,
        "beer": 250,
    }

    for key, price in expected_prices.items():
        assert VendingMachine.PRODUCTS[key][1] == price


# TEST 3 — Insert all 5 coin types
def test_all_coins(machine):

    coins = [("5", 5), ("10", 10), ("25", 25), ("100", 100), ("200", 200)]

    total = 0

    for key, value in coins:
        machine.event = key
        machine.update()
        total += value

    assert machine.amount == total
    assert machine.state.name == "add_coins"


# TEST 4 — Insufficient funds for a product
def test_insufficient_funds(machine):
    machine.event = "25"
    machine.update()

    machine.event = "chips"   # chips cost 200
    machine.update()

    # Must stay in add_coins, not deliver_product
    assert machine.state.name == "add_coins"
    assert machine.amount == 25


# TEST 5 — Successful purchase of a product
def test_successful_purchase(machine):

    # Insert $2.00
    machine.event = "200"
    machine.update()

    # Buy pop (125)
    machine.event = "pop"
    machine.update()

    assert machine.state.name == "deliver_product"

    # Run entry manually (same as GUI loop)
    machine.state.on_entry(machine)

    # Change: 200 - 125 = 75
    assert machine.change_due == 75
    assert machine.state.name == "count_change"

    # Run change output
    machine.update()
    assert machine.state.name == "waiting"


# TEST 6 — RETURN returns correct change
def test_return_button(machine):

    # Insert 1.00 + 0.25 = 1.25
    machine.event = "100"
    machine.update()
    machine.event = "25"
    machine.update()

    assert machine.amount == 125

    # Press RETURN
    machine.event = "RETURN"
    machine.update()

    # Should move to counting change
    assert machine.state.name == "count_change"
    assert machine.change_due == 125

    # Change returned: 100 + 25
    machine.update()
    assert machine.state.name == "waiting"



# TEST 7 — Complex change: 150 cents expected → 100 + 25 + 25
def test_complex_change(machine):

    # Insert: 100 + 25 + 25 = 150
    machine.event = "100"; machine.update()
    machine.event = "25"; machine.update()
    machine.event = "25"; machine.update()

    assert machine.amount == 150

    # Trigger RETURN
    machine.event = "RETURN"
    machine.update()

    assert machine.state.name == "count_change"
    assert machine.change_due == 150

    # Change returned until zero
    machine.update()
    assert machine.state.name == "waiting"

