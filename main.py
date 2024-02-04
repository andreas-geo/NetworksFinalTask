import socket
import os
import threading
import queue
import time

# Constants for UDP packet size and file transfer protocol
DEFAULT_TCP_PORT = 9000
DEFAULT_UDP_PORT = 9001
DISCOVERY_UDP_PORT = 9002
BROADCAST_ADDRESS = "255.255.255.255"
DISCOVERY_INTERVAL = 2  # Seconds

peer_list = []
last_heartbeat = {}

UDP_PACKET_SIZE = 1024  # Adjust as needed, keeping under the network's limit
FILE_TRANSFER_HEADER = "FILE:"
HEADER_LENGTH = 100  # Fixed length for the header

# Directory for files
files_dir = './uploads'

# Check if directory exists, if not, then create it
if not os.path.exists(files_dir):
    os.makedirs(files_dir)


# Servers Init
def tcp_server(port, message_queue):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind(('', port))
        server_socket.listen()

        while True:
            client_socket, addr = server_socket.accept()
            with client_socket:

                data = client_socket.recv(1024)

                if data.startswith(FILE_TRANSFER_HEADER.encode()):
                    try:
                        header = data.split(b":", 4)[:4]
                        header_decoded = ":".join(part.decode() for part in header)
                        _, username, filename, file_size = header_decoded.split(":")
                        file_size = int(file_size)

                        filedata = data[len(header_decoded) + 1:]  # +1 for the last colon

                        filepath = os.path.join(files_dir, filename)
                        with open(filepath, "wb") as file:
                            file.write(filedata)
                            remaining_size = file_size - len(filedata)

                            while remaining_size > 0:
                                chunk = client_socket.recv(min(1024, remaining_size))
                                if not chunk:
                                    break
                                file.write(chunk)
                                remaining_size -= len(chunk)

                        print(f"File received from {username}: {filename}")
                    except Exception as e:
                        print(f"Error processing file data from {addr}: {e}")
                else:
                    try:
                        message_queue.put({"type": "text", "data": f"TCP from {addr}: {data.decode()}"})
                    except UnicodeDecodeError:
                        print(f"Error decoding message from {addr}")


def udp_server(port, message_queue):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_socket:
        server_socket.bind(('', port))

        while True:

            data, addr = server_socket.recvfrom(1024)

            if data.startswith(FILE_TRANSFER_HEADER.encode()):
                # Directly put binary data in the queue without decoding
                message_queue.put({"type": "file", "data": data, "addr": addr})
            else:
                try:
                    # Handle text data as UTF-8
                    text_data = data.decode()
                    message_queue.put({"type": "text", "data": f"UDP from {addr}: {text_data}", "addr": addr})
                except UnicodeDecodeError:
                    print(f"Error decoding message from {addr}")


# Handle Message
def handle_messages(message_queue):
    while True:
        if not message_queue.empty():
            message = message_queue.get()
            if message["type"] == "file":
                try:
                    data = message["data"]
                    header = data[:HEADER_LENGTH].decode().strip()
                    filedata = data[HEADER_LENGTH:]

                    _, username, filename, file_index = header.split(":", 3)
                    filepath = os.path.join(files_dir, filename)
                    with open(filepath, "ab") as file:  # Append mode for assembling file chunks
                        file.write(filedata)

                    print(f"\n\nFile chunk received from {username}: {filename}\n")
                except Exception as e:
                    print(f"Error processing file data: {e}")

            elif message["type"] == "text":
                print("\n\n" + message["data"] + "\n")


# Messages
def send_message_to_peer(peer_index, port, message, username):
    if peer_index < 1 or peer_index > len(peer_list):
        print("Invalid peer selection.")
        return
    target_ip = peer_list[peer_index - 1][1]

    if port == DEFAULT_TCP_PORT:
        send_tcp_message(target_ip, port, message, username)
    else:
        send_udp_message(target_ip, port, message, username)


def send_tcp_message(address, port, message, username):
    complete_message = f"{username}: {message}"
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        client_socket.connect((address, port))
        client_socket.sendall(complete_message.encode())


def send_udp_message(address, port, message, username):
    complete_message = f"{username}: {message}"
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_socket:
        client_socket.sendto(complete_message.encode(), (address, port))


# Send a Message to All Peers
def send_p2p_message(peers, port, message, username):
    complete_message = f"{username}: {message}"
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_socket:
        for peer in peers:
            peer_ip = peer[1]  # Extract the IP address from the tuple
            client_socket.sendto(complete_message.encode(), (peer_ip, port))


# Send File Function
def send_file_to_peer(peer_index, port, file_path, username):
    if peer_index < 1 or peer_index > len(peer_list):
        print("Invalid peer selection.")
        return
    target_ip = peer_list[peer_index - 1][1]

    if file_path.endswith('.txt'):
        send_file_udp([target_ip], port, file_path, username)
    else:
        send_file_tcp([target_ip], port, file_path, username)


def send_file_tcp(peers, port, file_path, username):
    with open(file_path, "rb") as file:
        file_data = file.read()

    for peer in peers:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
                client_socket.connect((peer, port))
                header = f"{FILE_TRANSFER_HEADER}{username}:{os.path.basename(file_path)}:{len(file_data)}:"
                client_socket.sendall(header.encode() + file_data)
        except Exception as e:
            print(f"Error sending file to {peer}: {e}")


def send_file_udp(peers, port, file_path, username):
    with open(file_path, "rb") as file:
        file_index = 0
        while True:
            file_data = file.read(UDP_PACKET_SIZE - HEADER_LENGTH)
            if not file_data:
                break

            header_info = f"{username}:{os.path.basename(file_path)}:{file_index}:{len(file_data)}"
            header = f"{header_info:<{HEADER_LENGTH}}"  # Pad the header to a fixed length
            complete_message = header.encode() + file_data

            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_socket:
                for peer in peers:
                    client_socket.sendto(complete_message, (peer, port))

            file_index += 1


# Peer to Peer Advertising & Discovery
def discovery_broadcast(port, username):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while True:
            message = f"HEARTBEAT:{username}"
            s.sendto(message.encode(), (BROADCAST_ADDRESS, port))
            time.sleep(DISCOVERY_INTERVAL)


def discovery_listener(port, timeout=10):  # timeout in seconds
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('', port))
        while True:
            data, addr = s.recvfrom(UDP_PACKET_SIZE)
            current_time = time.time()

            if data.startswith(b"HEARTBEAT:"):
                peer_username = data.decode().split(":")[1]
                last_heartbeat[addr[0]] = current_time
                if addr[0] not in [peer[1] for peer in peer_list]:
                    peer_list.append((peer_username, addr[0]))

            # Remove peers that haven't sent a heartbeat in the last `timeout` seconds
            inactive_peers = [ip for ip, last_time in last_heartbeat.items() if current_time - last_time > timeout]
            for ip in inactive_peers:
                peer_list[:] = [(name, peer_ip) for name, peer_ip in peer_list if peer_ip != ip]
                del last_heartbeat[ip]


# Display Peers
def display_peers():
    print("\nConnected Peers:")
    for i, (username, ip) in enumerate(peer_list):
        print(f"{i + 1}. {username} - {ip}")


# Main Menu Function
def main_menu(username, tcp_port, udp_port, discovery_port, message_queue):
    threading.Thread(target=tcp_server, args=(tcp_port, message_queue), daemon=True).start()
    threading.Thread(target=udp_server, args=(udp_port, message_queue), daemon=True).start()
    threading.Thread(target=handle_messages, args=(message_queue,), daemon=True).start()

    threading.Thread(target=discovery_broadcast, args=(discovery_port, username), daemon=True).start()
    threading.Thread(target=discovery_listener, args=(discovery_port,), daemon=True).start()

    while True:
        print("\nMenu:")
        print("1. Send TCP message")
        print("2. Send UDP message")
        print("3. Send a File using TCP")
        print("4. Send a Text File using UDP (only for .txt )")
        print("5. Send P2P broadcast message (All Peers)")
        print("6. Display connected peers")
        print("7. Exit")

        choice = input("Enter your choice: ")

        if choice == '1':
            display_peers()
            peer_index = int(input("Select the number of the peer: "))
            message = input("Enter message to send over TCP: ")
            send_message_to_peer(peer_index, tcp_port, message, username)
        elif choice == '2':
            display_peers()
            peer_index = int(input("Select the number of the peer: "))
            message = input("Enter message to send over UDP: ")
            send_message_to_peer(peer_index, udp_port, message, username)
        elif choice == '3':
            display_peers()
            peer_index = int(input("Select the number of the peer: "))
            file_path = input("Enter file path: ")
            send_file_to_peer(peer_index, tcp_port, file_path, username)
        elif choice == '4':
            display_peers()
            peer_index = int(input("Select the number of the peer: "))
            file_path = input("Enter file path: ")
            send_file_to_peer(peer_index, udp_port, file_path, username)
        elif choice == '5':
            message = input("Enter message to broadcast to peers: ")
            send_p2p_message(peer_list, udp_port, message, username)
        elif choice == '6':
            display_peers()
        elif choice == '7':
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please try again.")


if __name__ == "__main__":
    user_name = input("Enter your username: ")
    tcp_port = int(DEFAULT_TCP_PORT)
    udp_port = int(DEFAULT_UDP_PORT)
    discovery_port = int(DISCOVERY_UDP_PORT)

    message_queue = queue.Queue()
    main_menu(user_name, tcp_port, udp_port, discovery_port, message_queue)