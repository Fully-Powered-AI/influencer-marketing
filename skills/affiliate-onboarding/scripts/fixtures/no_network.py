"""Run a script with every socket call refused, to show a branch makes no network call.

    python3 -I no_network.py SCRIPT [ARGS...]

Any attempt to open a connection or resolve a name raises, and the script fails loudly.
"""
import runpy
import socket
import sys


def refused(*args, **kwargs):
    raise RuntimeError("network call attempted in a branch that must not use the network")


socket.socket.connect = refused
socket.socket.connect_ex = refused
socket.create_connection = refused
socket.getaddrinfo = refused

script = sys.argv[1]
sys.argv = sys.argv[1:]
runpy.run_path(script, run_name="__main__")
