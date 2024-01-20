import socket
import os
import sys
import threading

# Default ports
TCP_PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
UDP_PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 8081

# Directory for files
files_dir = './files'

# Check if directory exists, if not, then create it
if not os.path.exists(files_dir):
    os.makedirs(files_dir)


# Function to start TCP Server
def start_tcp_server(port):
    try:
        tcp_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_server_socket.bind(('', port))
        tcp_server_socket.listen()
        print(f"TCP server listening on port {port}")

        while True:
            connection, client_address = tcp_server_socket.accept()
            # Handle connection in a new thread
            threading.Thread(target=handle_tcp_client, args=(connection,)).start()
    except Exception as e:
        print(f"An error occurred in the TCP server: {e}")


def handle_tcp_client(connection):
    try:
        while True:
            data = connection.recv(1024)
            if data:
                # Process data here
                print(f"Received message: {data}")
            else:
                break
    finally:
        connection.close()


# Function to start UDP Server
def start_udp_server(port):
    try:
        udp_server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_server_socket.bind(('', port))
        print(f"UDP server listening on port {port}")

        while True:
            data, address = udp_server_socket.recvfrom(1024)
            if data:
                # Process data here
                print(f"Received data: {data}")
    except Exception as e:
        print(f"An error occurred in the UDP server: {e}")


if __name__ == "__main__":
    # Starting servers in separate threads
    threading.Thread(target=start_tcp_server, args=(TCP_PORT,)).start()
    threading.Thread(target=start_udp_server, args=(UDP_PORT,)).start()
