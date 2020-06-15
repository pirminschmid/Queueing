"""
This TCP client connects with a the waiting callback server at ip:port.

It sends 'callback' and waits for a reply.

version 2018-10-14, Pirmin Schmid
"""

import socket
import sys

MAX_MESSAGE_LEN = 128

def main():
    if len(sys.argv) != 3:
        print('This tool connects with a waiting callback server at address <ip>, port <port>.')
        print('USAGE: {name} ip port'.format(name=sys.argv[0]))
        exit(1)
    ip = sys.argv[1]
    port = int(sys.argv[2])
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        try:
            client.connect((ip, port))
            client.sendall('callback'.encode())
            received = client.recv(MAX_MESSAGE_LEN)
        finally:
            pass


if __name__ == "__main__":
    main()
