import json
import os
import threading

from boolean import BooleanCircuit
from main import Alice, Bob
from typing import List

circuit_file = "alice_output.json"
verification_file = "verification.json"


class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def format_else(el):
    # bytes are not JSON-serializable so we convert those to hexadecimal
    return el.hex() if isinstance(el, bytes) else el


def format_dict(d):
    # format nested dictionaries to make them JSON-serializable
    r = {}
    for k, v in d.items():
        # Keys can only be one of these types, notably there are tuples as keys in the GarbledCircuit implementation,
        # so we convert those to strings.
        if type(k) not in [str, int, float, bool, None]:
            key = str(k)
        else:
            key = k
        if isinstance(v, bytes):
            # bytes are not JSON-serializable so we convert those to hexadecimal
            value = v.hex()
        elif isinstance(v, dict):
            # recursive formatting
            value = format_dict(v)
        elif isinstance(v, tuple):
            value = tuple(format_else(e) for e in v)
        elif isinstance(v, list):
            value = [format_else(e) for e in v]
        else:
            value = v
        r[key] = value
    return r


def print_alice_to_bob(alice: Alice):
    # In this implementation we only really ever have one circuit, but we keep this structure for compatibility
    for circuit in alice.circuits:
        # This is what gets sent to Bob for communication
        output = {
            "circuit": circuit["circuit"],
            "garbled_tables": circuit["garbled_tables"],
            "pbits_out": circuit["pbits_out"]
        }
        alice.socket.send_wait(output)
        # We add some more stuff that we want to save for inspection
        output["pbits"] = circuit["pbits"]
        output["keys"] = circuit["keys"]
        for key, element in output.items():
            clean = format_dict(element) if isinstance(element, dict) else format_else(element)
            output[key] = clean
        with open(circuit_file, "w") as fout:
            json.dump(output, fout)


def mpc_compute(alice: Alice):
    # In this implementation we only really ever have one circuit, but we keep this structure for compatibility
    for circuit in alice.circuits:
        # The bulk of operations happen in this function
        return alice.print(circuit)


def traditional_compute(a: List[int], b: List[int], bits: int):
    # Function to check what the true maximum is with base-10 maths in a non-multiparty way
    ss = []
    for i in range(0, len(a), bits):
        ss.append(int("".join([str(s) for s in a[i:i+bits]]), 2))
        ss.append(int("".join([str(s) for s in b[i:i+bits]]), 2))
    print("Full set:")
    print(f"{ss}")
    c = max(ss)
    return f"{c:0{bits}b}"


def verify_output(a, b):
    # Check correctness
    if a == b:
        return True
    else:
        return False


def main(bits: int = 4, set_size: int = 5, alice_input_file: str = "Alice.txt", bob_input_file: str = "Bob.txt"):

    # Define input circuit based on the parameters
    circuit = os.path.join(os.getcwd(), "circuits", f"max_{bits}bits_{set_size}items.json")

    if not os.path.exists(circuit):
        # If the input circuit hasn't been generated yet, we do it now
        circuit = BooleanCircuit(bits, set_size).complete_circuit()

    if not os.path.exists(alice_input_file):
        # Check if the input files exist
        print(f"{Colors.FAIL}{alice_input_file} (Alice's input file) not found!{Colors.ENDC}")
        exit(1)

    if not os.path.exists(bob_input_file):
        # Check if the input files exist
        print(f"{Colors.FAIL}{bob_input_file} (Bob's input file) not found!{Colors.ENDC}")
        exit(1)

    with open(alice_input_file, "r") as fin:
        # Alice's input
        bits_a = []
        # Read character by character and discard anything that is not a 0 or 1
        for line in fin.readlines():
            for character in line:
                if character == "1" or character == "0":
                    bits_a.append(int(character))
        # Ensure that the number of bits is a multiple of the set bit-length
        if len(bits_a) % bits != 0:
            print(f"{Colors.FAIL}Error in {alice_input_file}:{Colors.ENDC}")
            print(f"{Colors.FAIL}Numbers should be multiple of {bits} bits!{Colors.ENDC}")
            exit(1)
        # For maximum ease-of-use we pad or truncate the input to be of the correct set_size
        # Padding with all zeroes doesn't change the output of the function
        while len(bits_a) < set_size * bits:
            bits_a.append(0)
        while len(bits_a) > set_size * bits:
            bits_a.pop()

    with open(bob_input_file, "r") as fin:
        # Bob's input
        bits_b = []
        # Read character by character and discard anything that is not a 0 or 1
        for line in fin.readlines():
            for character in line:
                if character == "1" or character == "0":
                    bits_b.append(int(character))
        # Ensure that the number of bits is a multiple of the set bit-length
        if len(bits_b) % bits != 0:
            print(f"{Colors.FAIL}Error in {bob_input_file}:{Colors.ENDC}")
            print(f"{Colors.FAIL}Numbers should be multiple of {bits} bits!{Colors.ENDC}")
            exit(1)
        # For maximum ease-of-use we pad or truncate the input to be of the correct set_size
        # Padding with all zeroes doesn't change the output of the function
        while len(bits_b) < set_size * bits:
            bits_b.append(0)
        while len(bits_b) > set_size * bits:
            bits_b.pop()

    # String representation of the correct result
    correct_result = " ".join([b for b in traditional_compute(bits_a, bits_b, bits)])

    # We work with Alice who is responsible for generating the garbled circuit and sending it over to Bob
    alice = Alice(circuit, bits_a, bits)
    # Bob gets started in a separate thread and will be listening to Alice's communication on a local socket
    bob = Bob(bits_b, bits)
    t = threading.Thread(target=bob.listen)
    # Setting the thread as daemon allows it to quit when the program exits
    t.daemon = True
    t.start()

    # This function prints the necessary output from Alice that she wants to send to Bob
    # plus some additional information useful for debugging.
    # The output gets printed on a file named "alice_output.json"
    # The file is overwritten at each run of the script.
    # The output format and how to read it are described in the report document.
    print_alice_to_bob(alice)

    # Alice and Bob OT
    # This function prints in the console the OT between Alice and Bob that takes place in Yao's protocol.
    # It also prints the inputs and outputs that each party sees during the computation.
    result = mpc_compute(alice)

    # This function verifies whether the output from mpc_compute is same as the output
    # from a function which is computed non-multiparty way
    with open(verification_file, "w") as fout:
        fout.write(f"Expected output: {correct_result} ({int(correct_result.replace(' ', ''), 2)})\n")
        fout.write(f"Actual output: {result} ({int(result.replace(' ', ''), 2)})\n")
        fout.write(f"Correct: {verify_output(result, correct_result)}\n")

    print(f"Expected output: {correct_result} ({int(correct_result.replace(' ', ''), 2)})")
    print(f"Actual output: {result} ({int(result.replace(' ', ''), 2)})")
    correct = verify_output(result, correct_result)
    print(f"Correct: {Colors.OKGREEN if correct else Colors.FAIL}{correct}{Colors.ENDC}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run Yao protocol.")
    parser.add_argument(
        "-s",
        "--set-size",
        type=int,
        default=5,
        help="The size of the set of numbers for each party",
    )
    parser.add_argument(
        "-a",
        "--alice",
        type=str,
        default="Alice.txt",
        help="The file containing Alice's input numbers"
    )
    parser.add_argument(
        "-b",
        "--bob",
        type=str,
        default="Bob.txt",
        help="The file containing Bob's input numbers"
    )

    args = parser.parse_args()

    if args.set_size < 1 or args.set_size > 2 ** 4:
        print(f"{Colors.FAIL}Set size should be between 1 and {2**4}!{Colors.ENDC}")
        exit(1)

    # Bits are hard-coded to 4
    main(4, args.set_size, args.alice, args.bob)
