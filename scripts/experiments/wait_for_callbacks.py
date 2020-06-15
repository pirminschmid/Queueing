"""
This tool opens a TCP socket at a defined ip:port and waits until
it has received a defined number of connections (callback).

It waits for a message and replies with ACK.

In combination with the callback program, finished jobs can
properly be recognized to proceed to the next distributed task.

note: helpful for trouble-shooting: lsof -n -i

version 2018-10-14, Pirmin Schmid
"""

import socket
import sys

MAX_MESSAGE_LEN = 128


def main():
    if len(sys.argv) != 4:
        print('This tool waits for <count> TCP connections at address <ip>, port <port>.')
        print('USAGE: {name} ip port count'.format(name=sys.argv[0]))
        exit(1)
    ip = sys.argv[1]
    port = int(sys.argv[2])
    expected_count = int(sys.argv[3])
    print('waiting for {count} callbacks'.format(count=expected_count))

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((ip, port))
        backlog = expected_count + 1
        server.listen(backlog)
        received_count = 0
        while received_count < expected_count:
            try:
                client, client_address = server.accept()
                received_count += 1
                message = client.recv(MAX_MESSAGE_LEN)
                client.sendall('ACK'.encode())
            finally:
                client.close()
        print('all {count} callbacks received'.format(count=received_count))
        server.shutdown(socket.SHUT_RDWR)


if __name__ == "__main__":
    main()
