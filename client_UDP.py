"""
Thomas michalski
cs3357 - asn4
->client file for UDP chatroom connection. handles client side connection to server.
"""
import socket
import signal
import sys
import selectors
import os
import argparse
from urllib.parse import urlparse
import struct
import hashlib


# The default IP and port numbers to be changed in main
UDP_IP = 'localhost'
CLIENT_PORT = 0
SERVER_PORT = 0

# Setting a constant size for all packets
BUFFER_SIZE = 1024

# Define a maximum string size for the text we'll be sending along.
MAX_STRING_SIZE = 256

# Selector for helping us select incoming data from the server and messages typed in by the user.
sel = selectors.DefaultSelector()

# Socket for sending messages.
client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# User name for tagging sent messages.
user = ''

# Sequence number used by the RDT
sequence_number = 0


#gets the incoming message, converting it into a packet and send it to client
def send(message):#only needs one parameter because it will be only communicating with host
    global sequence_number
    from_port = CLIENT_PORT
    to_port = SERVER_PORT
    local = UDP_IP
    try:#incase we need to encode
        data = message.encode()
    except AttributeError:
        data = message
    size = len(data)
    
    #build packet for checksum
    packet_tuple = (sequence_number, from_port, size, data)
    packet_structure = struct.Struct(f'I I I {MAX_STRING_SIZE}s')
    packed_data = packet_structure.pack(*packet_tuple)
    checksums = bytes(hashlib.md5(packed_data).hexdigest(), encoding='UTF-8')
    
    #create packet
    packet_tuple = (sequence_number, from_port, size, data, checksums)
    UDP_packet_structure = struct.Struct(f'I I I {MAX_STRING_SIZE}s 32s')
    UDP_packet = UDP_packet_structure.pack(*packet_tuple)

    # Keep sending the packet if it is not received
    success = False
    while success == False:
        client_socket.sendto(UDP_packet, (local, to_port))

        # Wait for an ack message if we need one
        if message != 'ACK':
            ack = receive_packet()
            if ack == 'ACK':
                success = True
        else:
            success = True

    if sequence_number == 0:
        sequence_number = 1
    else:
        sequence_number = 0


#Read an incoming packet
def receive_packet():
    global sequence_number

    # We receive data and start to unpack it.  We'll use a 1024 byte buffer here.
    # Notice that our packet structure mirrors what the client is sending along.
    # The client and server have to agree on this or it won't work!
    try:
        received_packet, port = client_socket.recvfrom(BUFFER_SIZE)
    except TimeoutError:
        return ""
    unpacker = struct.Struct(f'I I I {MAX_STRING_SIZE}s 32s')
    UDP_packet = unpacker.unpack(received_packet)

    # Extract out data that was received from the packet.  It unpacks to a tuple,
    # but it's easy enough to split apart.
    received_sequence = UDP_packet[0]
    received_sender = UDP_packet[1]
    received_size = UDP_packet[2]
    received_data = UDP_packet[3]
    received_checksum = UDP_packet[4]

    # We now compute the checksum on what was received to compare with the checksum
    # that arrived with the data.  So, we repack our received packet parts into a tuple
    # and compute a checksum against that, just like we did on the sending side.
    if received_sequence == sequence_number:# check for sequence num
        values = (received_sequence, received_sender, received_size, received_data)
        packer = struct.Struct(f'I I I {MAX_STRING_SIZE}s')
        packed = packer.pack(*values)
        computed_checksum = bytes(hashlib.md5(packed).hexdigest(), encoding='UTF-8')


        # We can now compare the computed and received checksums to see if any corruption of
        # data can be detected.  Note that we only need to decode the data according to the
        # size we intended to send; the padding can be ignored.
        if received_checksum == computed_checksum:
            try:
                received_text = received_data[:received_size].decode().strip()
            except UnicodeDecodeError:
                received_text = received_data[:received_size]            
            
            if received_text != 'ACK':
                send('ACK')

            if sequence_number == 0:
                sequence_number = 1
            else:
                sequence_number = 0

            return received_text
        else:
            print('Received and computed checksums do not match, so packet is corrupt and discarded\n')
            return '', 0
    else:
        print('Received wrong sequence number, please try again\n')
        return '', 0


# Signal handler for graceful exiting.  Let the server know when we're gone.
# Signal handler for graceful exiting.  We let clients know in the process so they can disconnect too.
def signal_handler(sig, frame):
    print('Interrupt received, shutting down ...')
    message='DISCONNECT CHAT/1.0\n'
    send(message)     
    sys.exit(0)


# Simple function for setting up a prompt for the user.
def do_prompt(skipLine=False):
    if skipLine:
        print('')
    print('> ', end='', flush=True)

# Function to handle incoming messages from server.  Also look for disconnect messages to shutdown.
def handle_message_from_server(sock, mask):
    message = receive_packet()
    words = message.split(' ')
    
    if words[0] == 'DISCONNECT':
        print('Disconnected from server ... exiting!')
        sys.exit(0)
        
        
    # Handle file attachment request.
    
    elif words[0] == 'ATTACH':#gets file to be sent to server
        filename = words[1]
        try:
            file = open(filename, 'rb')#open file and read
            current_packet = file.read()

            file_size = os.path.getsize(filename)#get info on file
            total_packets = file_size // MAX_STRING_SIZE
            if file_size % MAX_STRING_SIZE:
                total_packets += 1

            header = f'{file_size} {MAX_STRING_SIZE} {total_packets}\n'
            send(header)

            while current_packet:# send packet one at a time
                dataPacket = current_packet[:MAX_STRING_SIZE]
                send(dataPacket)
                current_packet = current_packet[MAX_STRING_SIZE:]
            print(f'\nAttachment {filename} attached and distributed!')

        except IOError:
            print('File not found')
            response = 'ERROR'
            send(response)

    elif words[0] == 'ATTACHMENT':
        if len(words) == 6:
            filename = words[1]
            file_sender = words[2]
            file_size = int(words[3])
            total_packets = int(words[5])
            print(f'\nIncoming file: {filename}')
            print(f'Origin: {file_sender}')
            print(f'Content-Length: {file_size}')

            file = open(filename, 'wb')

            for _ in range(0, total_packets):
                packet = receive_packet()
                try:
                    file.write(packet)
                except TypeError:
                    file.write(packet.encode())

            file.close()
            print('File received!')

        else:
            print('Could not receive file correctly.')

    else:
        print(message)

    do_prompt()


# Function to handle incoming messages from user.
def handle_keyboard_input(file, mask):
    line = sys.stdin.readline()
    message = f'@{user}: {line}'
    send(message)
    do_prompt()


# Our main function.
def main():
    global user
    global client_socket

    global UDP_IP
    global SERVER_PORT
    global CLIENT_PORT

    # Register our signal handler for shutting down.
    signal.signal(signal.SIGINT, signal_handler)

    # Check command line arguments to retrieve a URL.
    parser = argparse.ArgumentParser()
    parser.add_argument('user', help='user name for this user on the chat service')
    parser.add_argument('server', help='URL indicating server location in form of chat://host:port')
    parser.add_argument('-f', '--follow', nargs=1, default=[], help="comma separated list of users/topics to follow")

    args = parser.parse_args()

    # Check the URL passed in and make sure it's valid.  If so, keep track of
    # things for later.
    try:
        server = urlparse(args.server)
        if server.scheme != 'chat' or server.port is None or server.hostname is None:
            raise ValueError
        host = server.hostname
        port = server.port
    except ValueError:
        print('Error:  Invalid server.  Enter a URL of the form:  chat://host:port')
        sys.exit(1)
    user = args.user
    follow = args.follow


    # Now we try to set up a datagram with the server.
    print('Connecting to server ...')
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client_socket.bind((host, 0))
        CLIENT_PORT = client_socket.getsockname()[1]
        client_socket.setblocking(True)
        client_socket.settimeout(2000)
    except ConnectionRefusedError:
        print('Error:  That host or port is not accepting connections.')
        sys.exit(1)
        
    UDP_IP = host
    SERVER_PORT = port
    
    # The connection was successful, so we can prep and send a registration message.
    print('Connection to server established. Sending intro message...\n')
    message = f'REGISTER {user} CHAT/1.0\n'
    send(message)
    
    #If we have terms to follow, we send them now.  Otherwise, we send an empty line to indicate we're done with registration.
    if follow != []:
        fmessage = f'Follow: {follow[0]}\n\n'
        send(fmessage)
    
    # Receive the response from the server and start taking a look at it
    response_line = receive_packet()
    response_list = response_line.split(' ')

    # If an error is returned from the server, we dump everything sent and
    # exit right away.
    if response_list[0] != '200':
        print('Error:  An error response was received from the server.  Details:\n')
        print(response_line)
        print('Exiting now ...')
        sys.exit(1)
    else:
        print('Registration successful.  Ready for messaging!')

    # Set up our selector.
    sel.register(sys.stdin, selectors.EVENT_READ,handle_keyboard_input)
    sel.register(client_socket,selectors.EVENT_READ,handle_message_from_server)

    # Prompt the user before beginning.
    do_prompt()

    # Now do the selection.
    while(True):
        events = sel.select()
        for key, mask in events:
            callback = key.data
            callback(key.fileobj, mask) 


if __name__ == '__main__':
    main()
