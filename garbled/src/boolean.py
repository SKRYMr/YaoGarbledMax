import json
import os


def truth_table(b):
    # Function to compute the truth table of the max function for any number of input bits
    table = []
    for x in range(2 ** b):
        for y in range(2 ** b):
            table.append(f"{x:0{b}b}|{y:0{b}b}|{max(x,y):0{b}b}")


class BooleanCircuit:

    def __init__(self, bits: int = 4, set_size: int = 1):
        self.bits = bits
        self.set_size = set_size
        self.gen = self.get_next_id(2 * self.bits)
        self.inputs_alice = []
        self.inputs_bob = []
        self.outputs = []
        self.gates = []

    @staticmethod
    def get_next_id(start: int = 8):
        # Generator for the gate number, starts from the one after the last input
        gate_n = start
        while True:
            gate_n += 1
            yield gate_n

    def an(self, a: int, b: int, output: bool = False):
        # Generate an "AND" gate
        out = self.gen.__next__()
        self.gates.append({"id": out, "type": "AND", "in": [a, b]})
        if output:
            self.outputs.append(out)
        return out

    def nxor(self, a: int, b: int, output: bool = False):
        # Generate an "NXOR" gate
        out = self.gen.__next__()
        self.gates.append({"id": out, "type": "NXOR", "in": [a, b]})
        if output:
            self.outputs.append(out)
        return out

    def no(self, a: int, output: bool = False):
        # Generate a "NOT" gate
        out = self.gen.__next__()
        self.gates.append({"id": out, "type": "NOT", "in": [a]})
        if output:
            self.outputs.append(out)
        return out

    def orr(self, a: int, b: int, output: bool = False):
        # Generate an "OR" gate
        out = self.gen.__next__()
        self.gates.append({"id": out, "type": "OR", "in": [a, b]})
        if output:
            self.outputs.append(out)
        return out

    def circuit_block(self, a3, a2, a1, a0, b3, b2, b1, b0):
        # A single circuit to compare two 4-bit values

        # Create local aliases for functions to make code more compact and legible
        nxor = self.nxor
        no = self.no
        an = self.an
        orr = self.orr

        # NXOR to check which bits are equal
        x3 = nxor(a3, b3)
        x2 = nxor(a2, b2)
        x1 = nxor(a1, b1)
        x0 = nxor(a0, b0)

        # NOTs useful later
        nb0 = no(b0)
        nb1 = no(b1)
        nb2 = no(b2)
        nb3 = no(b3)

        # Z tells us whether the two numbers are equal
        z = an(an(x3, x2), an(x1, x0))

        # X is true if A > B
        x = orr(
                orr(
                    orr(
                        an(a3, nb3), an(an(x3, a2), nb2)
                    ),
                    an(an(x3, x2), an(a1, nb1))
                ),
                an(an(an(an(x3, x2), x1), a0), nb0)
            )

        # If A > B or A = B we output A
        x = orr(x, z)
        nx = no(x)

        # Set the correct output bits
        z3 = orr(a3, b3, output=True)
        z2 = orr(an(x, a2), an(nx, b2), output=True)
        z1 = orr(an(x, a1), an(nx, b1), output=True)
        z0 = orr(an(x, a0), an(nx, b0), output=True)

        return z3, z2, z1, z0

    def complete_circuit(self, debug: bool = False):
        # Iteratively assembles a circuit to compare an arbitrarily large number of 4-bit values
        # Number of inputs is equal to twice the set size (set_size for each participant)
        n = self.set_size * 2
        # Starting 4 bit input for Alice
        alice = True
        a3, a2, a1, a0 = 1, 2, 3, 4
        self.inputs_alice.extend([a3, a2, a1, a0])
        # Starting 4 bit input for Bob
        b3, b2, b1, b0 = 5, 6, 7, 8
        self.inputs_bob.extend([b3, b2, b1, b0])
        # Loop over the block circuit and add a new input at each iteration
        for i in range(n-2):
            a3, a2, a1, a0 = self.circuit_block(a3, a2, a1, a0, b3, b2, b1, b0)
            b3 = self.gen.__next__()
            b2 = self.gen.__next__()
            b1 = self.gen.__next__()
            b0 = self.gen.__next__()
            # Add input gates to the respective participant
            if alice:
                self.inputs_alice.extend([b3, b2, b1, b0])
            else:
                self.inputs_bob.extend([b3, b2, b1, b0])
            # Switch participant halfway through
            if (n-2) / (i+1) == 2:
                alice = not alice

        # Last block computes output
        self.circuit_block(a3, a2, a1, a0, b3, b2, b1, b0)

        # Format circuit JSON
        output_file = os.path.join(os.getcwd(), "circuits", f"max_{self.bits}bits_{int(n/2)}items.json")
        json_format = {
            "name": "max",
            "circuits": [
                {
                    "id": f"{self.bits}-bits MAX with {n} elements",
                    "alice": self.inputs_alice,
                    "bob": self.inputs_bob,
                    "out": self.outputs[-4:],
                    "gates": self.gates
                }
            ]
        }

        # Print everything for debugging purposes
        if debug:
            print(len(self.inputs_alice))
            print(len(self.inputs_bob))
            print(self.inputs_alice)
            print(self.inputs_bob)
            print(json.dumps(self.outputs[-4:]))
            print(json.dumps(self.gates))

        # Save the circuit
        with open(output_file, "w+") as fout:
            json.dump(json_format, fout)

        return output_file
