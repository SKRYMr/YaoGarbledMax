#!/usr/bin/env python3
import logging
import ot
import util
import yao
from abc import ABC, abstractmethod

logging.basicConfig(format="[%(author)s] %(message)s",
                    level=logging.DEBUG)


class YaoGarbler(ABC):
    """An abstract class for Yao garblers (e.g. Alice)."""
    def __init__(self, circuits):
        circuits = util.parse_json(circuits)
        self.name = circuits["name"]
        self.circuits = []

        for circuit in circuits["circuits"]:
            garbled_circuit = yao.GarbledCircuit(circuit)
            pbits = garbled_circuit.get_pbits()
            entry = {
                "circuit": circuit,
                "garbled_circuit": garbled_circuit,
                "garbled_tables": garbled_circuit.get_garbled_tables(),
                "keys": garbled_circuit.get_keys(),
                "pbits": pbits,
                "pbits_out": {w: pbits[w]
                              for w in circuit["out"]},
            }
            self.circuits.append(entry)


class Alice(YaoGarbler):
    """Alice is the creator of the Yao circuit.

    Alice creates a Yao circuit and sends it to the evaluator along with her
    encrypted inputs. Alice will finally print the truth table of the circuit
    for all combination of Alice-Bob inputs.

    Alice does not know Bob's inputs but for the purpose
    of printing the truth table only, Alice assumes that Bob's inputs follow
    a specific order.

    Attributes:
        circuits: the JSON file containing circuits
        input_bits: the bits that correspond to Alice's input
        bits: the size of the numbers in bits
        oblivious_transfer: Optional; enable the Oblivious Transfer protocol
            (True by default).
    """
    def __init__(self, circuits, input_bits, bits, oblivious_transfer=True):
        super().__init__(circuits)
        self.in_bits = input_bits
        self.bits = bits
        self.socket = util.GarblerSocket()
        self.ot = ot.ObliviousTransfer(self.socket, enabled=oblivious_transfer)

    def print(self, entry):
        """Print circuit evaluation for all Bob and Alice inputs.

        Args:
            entry: A dict representing the circuit to evaluate.
        """
        circuit, pbits, keys = entry["circuit"], entry["pbits"], entry["keys"]
        outputs = circuit["out"]
        a_wires = circuit.get("alice", [])  # Alice's wires
        a_inputs = {}  # map from Alice's wires to (key, encr_bit) inputs
        b_wires = circuit.get("bob", [])  # Bob's wires
        b_keys = {  # map from Bob's wires to a pair (key, encr_bit)
            w: self._get_encr_bits(pbits[w], key0, key1)
            for w, (key0, key1) in keys.items() if w in b_wires
        }

        print(f"======== {circuit['id']} ========")

        for i in range(len(a_wires)):
            a_inputs[a_wires[i]] = (keys[a_wires[i]][self.in_bits[i]],
                                    pbits[a_wires[i]] ^ self.in_bits[i])

        result = self.ot.get_result(a_inputs, b_keys)
        str_result = ' '.join([str(result[w]) for w in outputs])
        str_in_bits = ''.join([str(b) for b in self.in_bits])

        print(f"Alice{a_wires} =")
        for i in range(0, len(str_in_bits), self.bits):
            print(f"{' '.join(str_in_bits[i:i+self.bits])} ({int(str_in_bits[i:i+self.bits], 2)})")
        print(f"Outputs{outputs} = {str_result} ({int(str_result.replace(' ', ''), 2)})")

        return str_result

    def _get_encr_bits(self, pbit, key0, key1):
        return ((key0, 0 ^ pbit), (key1, 1 ^ pbit))


class Bob:
    """Bob is the receiver and evaluator of the Yao circuit.

    Bob receives the Yao circuit from Alice, computes the results and sends
    them back.

    Args:
        input_bits: the bits that correspond to Bob's input
        bits: the size of the numbers in bits
        oblivious_transfer: Optional; enable the Oblivious Transfer protocol
            (True by default).
    """
    def __init__(self, input_bits, bits, oblivious_transfer=True):
        self.in_bits = input_bits
        self.bits = bits
        self.socket = util.EvaluatorSocket()
        self.ot = ot.ObliviousTransfer(self.socket, enabled=oblivious_transfer)

    def listen(self):
        """Start listening for Alice messages."""
        logging.info("Start listening", extra={"author": "BOB"})
        try:
            for entry in self.socket.poll_socket():
                self.socket.send(True)
                self.send_evaluation(entry)
        except KeyboardInterrupt:
            logging.info("Stop listening", extra={"author": "BOB"})

    def send_evaluation(self, entry):
        """Evaluate yao circuit for all Bob and Alice's inputs and
        send back the results.

        Args:
            entry: A dict representing the circuit to evaluate.
        """
        circuit, pbits_out = entry["circuit"], entry["pbits_out"]
        garbled_tables = entry["garbled_tables"]
        b_wires = circuit.get("bob", [])  # list of Bob's wires

        print(f"Received {circuit['id']}")

        # Create dict mapping each wire of Bob to Bob's input
        b_inputs_clear = {
            b_wires[i]: self.in_bits[i]
            for i in range(len(b_wires))
        }

        str_in_bits = ''.join([str(b) for b in self.in_bits])

        # Evaluate and send result to Alice
        self.ot.send_result(circuit, garbled_tables, pbits_out, b_inputs_clear)
        print(f"Bob{b_wires} =")
        for i in range(0, len(str_in_bits), self.bits):
            print(f"{' '.join(str_in_bits[i:i+self.bits])} ({int(str_in_bits[i:i+self.bits], 2)})")
