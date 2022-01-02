"""
Thomas michalski
cs3357 - asn4
->server file for UDP chatroom connection. handles server side connection to allow communication and packet transfering with clients.
"""
import socket
import os
import datetime
import signal
import sys
import selectors
from string import punctuation
import struct
import hashlib

# Constant for our buffer size
BUFFER_SIZE = 1024

UDP_IP = 'localhost'
UDP_PORT = 0

# Define a maximum string size for the text we'll be receiving.
MAX_STRING_SIZE = 256

# Selector for helping us select incoming data and connections from multiple sources.
sel = selectors.DefaultSelector()

# Client list for mapping connected clients to their connections.
client_list = []

follow_terms = []

#socket
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Sequence number
sequence_number = 0


# Signal handler for graceful exiting.  We let clients know in the process so they can disconnect too.
def signal_handler(sig, frame):
    print('Interrupt received, shutting down ...')
    message='DISCONNECT CHAT/1.0\n'
    for reg in client_list:
        send(message, reg[1])
        
    sys.exit(0)


# Search the client list for a particular user.
def client_search(user):
    for reg in client_list:
        if reg[0] == user:
            return reg[1]
    return None

# Search the client list for a particular user by their socket.
def client_search_by_socket(sock):
    for reg in client_list:
        if reg[1] == sock:
            return reg[0]
    return None

# Add a user to the client list.

def client_add(user, conn, follow_terms):
    registration = (user, conn, follow_terms)
    client_list.append(registration)

# Remove a client when disconnected.
def client_remove(user):
    for reg in client_list:
        if reg[0] == user:
            client_list.remove(reg)
            break

# Function to list clients.
def list_clients():
    first = True
    list = ''
    for reg in client_list:
        if first:
            list = reg[0]
            first = False
        else:
            list = f'{list}, {reg[0]}'
    return list

# Function to return list of followed topics of a user.
def client_follows(user):
    for reg in client_list:
        if reg[0] == user:
            first = True
            list = ''
            for topic in reg[2]:
                if first:
                    list = topic
                    first = False
                else:
                    list = f'{list}, {topic}'
            return list
    return None

# Function to add to list of followed topics of a user, returning True if added or False if topic already there.
def client_add_follow(user, topic):
    for reg in client_list:
        if reg[0] == user:
            if topic in reg[2]:
                return False
            else:
                reg[2].append(topic)
                return True
    return None

# Function to remove from list of followed topics of a user, returning True if removed or False if topic was not already there.
def client_remove_follow(user, topic):
    for reg in client_list:
        if reg[0] == user:
            if topic in reg[2]:
                reg[2].remove(topic)
                return True
            else:
                return False
    return None


#gets the incoming message, converting it into a packet and send it to client
def send(message, to_port):
    global sequence_number
    from_port = UDP_PORT
    local = UDP_IP
    
    try:
        packet = message.encode()
    except AttributeError:
        packet = message
    size = len(packet)
    
    #build packet for checksum
    packet_tuple = (sequence_number, from_port, size, packet)
    packet_structure = struct.Struct(f'I I I {MAX_STRING_SIZE}s')
    packed_data = packet_structure.pack(*packet_tuple)
    checksum = bytes(hashlib.md5(packed_data).hexdigest(), encoding='UTF-8')
    
    #create packet
    packet_tuple = (sequence_number, from_port, size, packet, checksum)
    UDP_packet_structure = struct.Struct(f'I I I {MAX_STRING_SIZE}s 32s')
    UDP_packet = UDP_packet_structure.pack(*packet_tuple)

    # Keep sending the packet if it is not received
    success = False
    while success == False:
        server_socket.sendto(UDP_packet, (local, to_port))

        # Wait for an ack message if we need one
        if message != 'ACK':
            ack = receive_packet()[0]
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
        receive_packet, port = server_socket.recvfrom(BUFFER_SIZE)
    except TimeoutError:
        return ""
    unpacker = struct.Struct(f'I I I {MAX_STRING_SIZE}s 32s')
    UDP_packet = unpacker.unpack(receive_packet)

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
    values = (received_sequence, received_sender, received_size, received_data)
    packer = struct.Struct(f'I I I {MAX_STRING_SIZE}s')
    packed = packer.pack(*values)
    computed_checksum = bytes(hashlib.md5(packed).hexdigest(), encoding='UTF-8')


    if received_sequence == sequence_number:# check for sequence num
        # We can now compare the computed and received checksums to see if any corruption of
        # data can be detected.  Note that we only need to decode the data according to the
        # size we intended to send; the padding can be ignored.
        if received_checksum == computed_checksum:
            print('Checksums match')
            try:
                received_text = received_data[:received_size].decode().strip()
            except UnicodeDecodeError:
                received_text = received_data[:received_size]            
            
            if received_text != 'ACK':
                send('ACK', received_sender)
                print(f'Message text was:  {received_text}')

            if sequence_number ==0:
                sequence_number =1
            else:
                sequence_number =0

            return received_text, received_sender
        
        #doesnt allow user to join
        else:
            print('Received and computed checksums do not match, so packet is corrupt and discarded\n')
            return '', 0
    else:
        print('Received wrong sequence number, please try again\n')
        return '', 0

# Function to read messages from clients.
def read_message(message, sock, mask):
    
    # Closed connection
    if message == '':
        print('Closing connection')
        sel.unregister(sock)
        sock.close()

    # Receive the message.  
    else:
        user = client_search_by_socket(sock)
        print(f'Received message from user {user}: ' +message)
        words = message.split(' ')

        # Check for client disconnections.  
        if words[0] == 'DISCONNECT':
            print('Disconnecting user ' + user)
            client_remove(user)

        # Check for specific commands.
        elif ((len(words) == 2) and ((words[1] == '!list') or (words[1] == '!exit') or (words[1] == '!follow?'))):
            if words[1] == '!list':
                response = list_clients() + '\n'
                client_port = client_search(user)
                send(response, client_port)
            elif words[1] == '!exit':
                print('Disconnecting user ' + user)
                response='DISCONNECT CHAT/1.0\n'
                client_port = client_search(user)
                send(response, client_port)
                client_remove(user)
            elif words[1] == '!follow?':
                response = client_follows(user) + '\n'
                client_port = client_search(user)
                send(response, client_port)
                
        # Check for specific commands with a parameter.
        elif ((len(words) == 3) and ((words[1] == '!follow') or (words[1] == '!unfollow'))):
            if words[1] == '!follow':
                topic = words[2]
                if client_add_follow(user, topic):
                    response = f'Now following {topic}\n'
                else:
                    response = f'Error:  Was already following {topic}\n'
                client_port = client_search(user)
                send(response, client_port)
            elif words[1] == '!unfollow':
                topic = words[2]
                if topic == '@all':
                    response = 'Error:  All users must follow @all\n'
                elif topic == '@'+user:
                    response = 'Error:  Cannot unfollow yourself\n'
                elif client_remove_follow(user, topic):
                    response = f'No longer following {topic}\n'
                else:
                    response = f'Error:  Was not following {topic}\n'
                client_port = client_search(user)
                send(response, client_port)

        # Check for user trying to upload/attach a file.  We strip the message to keep the user and any other text to help forward the file.  Will
        # send it to interested users like regular messages.
        elif ((len(words) >= 3) and (words[1] == '!attach')):
            
            filename = words[2]
            words.remove('!attach')
            words.remove(filename)
            response =f'ATTACH {filename} CHAT/1.0\n'
            client_port = client_search(user)
            send(response, client_port)
            header =receive_packet()[0]
            header = header.split(' ')
            
            
            if len(header)== 3:
                
                #give info on file
                file_size = int(header[0])
                packet_size = int(header[1])
                total_packets= int(header[2])

                file_packets =receive_packet()[0]# getting errors if I do not add?
                print(f'Received packet from {filename}\n')

                # iterate for each packet
                for i in range(1,total_packets):
                    try:
                        packet =receive_packet()[0]
                        try:# incase it needs encoding
                            file_packets+= packet
                        except TypeError:
                            file_packets+= packet.encode()
                        print(str(i)+ ' ' + str(total_packets))
                        print('Received packet\n')
                    except:
                        print('errorrrr')
                        packet =receive_packet()[0]
                        try:# incase it needs encoding
                            file_packets+= packet
                        except TypeError:
                            file_packets+= packet.encode()
                        

                print(f'Recieved all packets from: {filename}')

                # select the clients to send to
                for reg in client_list:
                    if reg[0] == user:
                        continue
                    included_terms = words[0:]# check who user wanted to send it to
                    forwarded = False
                    
                    # determine if the client has a term followed from the sender
                    
                    for term in reg[2]:
                        for word in included_terms:
                            if ((term == word.rstrip(punctuation)) and not forwarded):
                                forwarded = True
                                
                    #if client is following a term from the sender, send the file
                    if forwarded == True:
                        message = f'ATTACHMENT {filename} {user} {file_size} {packet_size} {total_packets}\n'
                        client_port = client_search(reg[0])
                        send(message, client_port)
                        
                        print(f'Now sending packet from file {filename} to {reg[0]}')
                        current_packet = file_packets
                        while current_packet:
                            dataPacket = current_packet[:packet_size]
                            client_port = client_search(reg[0])
                            send(dataPacket, client_port)
                            current_packet = current_packet[packet_size:]

                        print(f'Attachment {filename} distributed to: {reg[0]}')
            else:#error with attachment
                print('Error with file')
                    
        # Look for follow terms and dispatch message to interested users.  Send at most only once, and don't send to yourself.  Trailing punctuation is stripped.
        # Need to re-add stripped newlines here.
        else:
            for reg in client_list:
                if reg[0] == user:
                    continue
                forwarded = False
                for term in reg[2]:
                    for word in words:
                        if ((term == word.rstrip(punctuation)) and not forwarded):
                            client_sock = reg[1]
                            forwarded_message = f'{message}\n'
                            send(forwarded_message, client_sock)
                            forwarded = True
        



# Function to accept and set up clients.

def accept_client(message, port, mask):
    
    message_parts = message.split()

    # If we have received a register request
    if message_parts[0] == 'REGISTER':
        print('Accepted connection from client')
        user = message_parts[1]
        follow_terms = []
        # Check format of request.
        if len(message_parts) == 3 and message_parts[0] == 'REGISTER' and message_parts[1] != 'all' and message_parts[2] == 'CHAT/1.0':
            user = message_parts[1]
            if user == 'all':
                print('Error:  Client cannot use reserved user name \'all\'.')
                print('Connection closing ...')
                response='402 Forbidden user name\n'
                send(response, port)
            elif client_search(user) == None:
                follow_terms.append(f'@{user}')
                follow_terms.append('@all')
                client_add(user, port, follow_terms)
                print(f'Connection to client established, waiting to receive messages from user \'{user}\'...')
                response = '200 Registration successful\n'
                send(response, port)
                
            # If user already in list, return a registration error.
            else:
                print('Error:  Client already registered.')
                print('Connection closing ...')
                response = '401 Client already registered\n'
                send(response, port)

        # Registration is incorrectly formatted.
        else:
            print('Error: Invalid registration message.')
            print(f'Received: {message}')
            print('Connection closing ...')
            response = '400 Invalid registration\n'
            send(response, port)
    
    
    
#checks if new user, else handles messages
def handle_message(sock, mask):
    message, port = receive_packet()
    if message.startswith('REGISTER'):
        accept_client(message, port, mask)
    else:       
        read_message(message, port,mask)



# Our main function.
def main():
    global UDP_PORT
    global server_socket
    # Register our signal handler for shutting down.

    signal.signal(signal.SIGINT, signal_handler)

    # Create the socket.  We will ask this to work on any interface and to pick
    # a free port at random.  We'll print this out for clients to use.
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except ConnectionRefusedError:
        print("Error:  That socket error.")
        sys.exit(1)
    server_socket.bind((UDP_IP, 0))
    UDP_PORT = server_socket.getsockname()[1]
    server_socket.setblocking(True)
    server_socket.settimeout(1000)
    
    print('Will wait for client connections at port ' + str(UDP_PORT))
    sel.register(server_socket, selectors.EVENT_READ, handle_message)
    print('Waiting for incoming client connections ...')
    
    # Keep the server running forever, waiting for connections or messages.
    while(True):
        events = sel.select()
        for key, mask in events:
            callback = key.data
            callback(key.fileobj, mask)    

if __name__ == '__main__':
    main()




