"""
Thomas michalski
cs3357 - asn3
Nov 9th, 2021
->client file for tcp chatroom connection. handles client side connection to server.
"""
#!/usr/bin/env python3

import socket
import os
import signal
import sys
import argparse
from urllib.parse import urlparse
import selectors

BUFFER_SIZE = 4096
# Selector for helping us select incoming data from the server and messages typed in by the user.

sel = selectors.DefaultSelector()

# Socket for sending messages.

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# User name for tagging sent messages.

user = ''

# Signal handler for graceful exiting.  Let the server know when we're gone.

def signal_handler(sig, frame):
    print('Interrupt received, shutting down ...')
    message=f'DISCONNECT {user} CHAT/1.0\n'
    client_socket.send(message.encode())
    sys.exit(0)

# Simple function for setting up a prompt for the user.

def do_prompt(skip_line=False):
    if (skip_line):
        print("")
    print("> ", end='', flush=True)

# Read a single line (ending with \n) from a socket and return it.
# We will strip out any \r and \n in the process.

def get_line_from_socket(sock):
    done = False
    line = ''
    while (not done):
        char = sock.recv(1).decode()
        if (char == '\r'):
            pass
        elif (char == '\n'):
            done = True
        else:
            line = line + char
    return line

# handles incoming file transfers incoming from the server
def receive(words, sock):
    
    sock.setblocking(True)
    
    try: # receiving should contain a length of 6 if done correct. get info on file.
        if (len(words) == 6):
            file_name = words[1]
            sending_user = words[2]
            size = int(words[3])
            packet_size = int(words[4])
            number_of_packets = int(words[5])
            print(f'\nIncoming file: {file_name}')
            print(f'Origin: {sending_user}')
            print(f'Content-Length: {size}')
            
            try:# create new file and write incoming data to it.
                file = open(file_name, 'w')
                data = ''
                for i in range(0, number_of_packets):
                    packet = sock.recv(packet_size).decode('ISO-8859-1')
                    file.write(packet)
                    data = data + packet
                file.close()
            except:
                print('error writing incoming data to new file')
    except:
        print('error receiving file from server')
        # else:
        #     print('Could not recieve file correctly.')
    sock.setblocking(False)
    
# handles sending out data from files to server
def send(file_name, sock):
    sock.setblocking(True)
    try:
        file = open(file_name, 'rb') # opens files chosen by user to send
        data= file.read().decode('ISO-8859-1')
        
        # gets size of the data in the fileand finds number of packets needed
        size = len(data)
        number_of_packets = size //BUFFER_SIZE
        if size % BUFFER_SIZE:
            number_of_packets += 1
            
        file_specs = (f'{size} {BUFFER_SIZE} {number_of_packets}\n')
        sock.send(file_specs.encode())
        
        try: # sends packets to server
            while (data != ''):
                data_packet = data[:BUFFER_SIZE]
                sock.send(data_packet.encode())
                data = data[BUFFER_SIZE:]
            print(f'\nAttachment {file_name} attached and distributed\n')
            do_prompt()
        except:
            print('error sending packets')
    except IOError:
        print('Error: cannot open file')
        sock.send('Error, cannot send open file'.encode())
        pass
    sock.setblocking(False)
        
    

# Function to handle incoming messages from server.  Also look for disconnect messages to shutdown.
def handle_message_from_server(sock, mask):
    message=get_line_from_socket(sock)
    words=message.split(' ')
    print()
    if words[0] == 'DISCONNECT': # if it is disconnect message
        print('Disconnected from server ... exiting!')
        sys.exit(0)
    elif words[0] == 'SEND': # check if file is being sent out
        send(words[1], sock)
    elif words[0] == 'RECEIVE': # check if file is being recieved
        receive(words, sock)
    else:
        print(message)
        do_prompt()

# Function to handle incoming messages from user.

def handle_keyboard_input(file, mask):
    line=sys.stdin.readline()
    message = f'@{user}: {line}'
    client_socket.send(message.encode())
    do_prompt()

# Our main function.

def main():

    global user
    global client_socket

    # Register our signal handler for shutting down.

    signal.signal(signal.SIGINT, signal_handler)

    # Check command line arguments to retrieve a URL.

    parser = argparse.ArgumentParser()
    parser.add_argument("user", help="user name for this user on the chat service")
    parser.add_argument("server", help="URL indicating server location in form of chat://host:port")
    args = parser.parse_args()

    # Check the URL passed in and make sure it's valid.  If so, keep track of
    # things for later.

    try:
        server_address = urlparse(args.server)
        if ((server_address.scheme != 'chat') or (server_address.port == None) or (server_address.hostname == None)):
            raise ValueError
        host = server_address.hostname
        port = server_address.port
    except ValueError:
        print('Error:  Invalid server.  Enter a URL of the form:  chat://host:port')
        sys.exit(1)
    user = args.user

    # Now we try to make a connection to the server.

    print('Connecting to server ...')
    try:
        client_socket.connect((host, port))
    except ConnectionRefusedError:
        print('Error:  That host or port is not accepting connections.')
        sys.exit(1)

    # The connection was successful, so we can prep and send a registration message.
    
    print('Connection to server established. Sending intro message...\n')
    message = f'REGISTER {user} CHAT/1.0\n'
    client_socket.send(message.encode())
   
    # Receive the response from the server and start taking a look at it

    response_line = get_line_from_socket(client_socket)
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

    client_socket.setblocking(False)
    sel.register(client_socket, selectors.EVENT_READ, handle_message_from_server)
    sel.register(sys.stdin, selectors.EVENT_READ, handle_keyboard_input)
    
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