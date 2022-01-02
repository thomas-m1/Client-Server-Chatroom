"""
Thomas michalski
cs3357 - asn3
Nov 9th, 2021
->server file for tcp chatroom connection. allows connection for multiple devices, follow terms, and send attachments over tcp.
"""
#!/usr/bin/env python3

import socket
import os
import signal
import sys
import selectors

# Selector for helping us select incoming data and connections from multiple sources.

sel = selectors.DefaultSelector()

# Client list for mapping connected clients to their connections.

client_list = []
user_name_list = []
dict = {}

# Signal handler for graceful exiting.  We let clients know in the process so they can disconnect too.

def signal_handler(sig, frame):
    print('Interrupt received, shutting down ...')
    message='DISCONNECT CHAT/1.0\n'
    for reg in client_list:
        reg[1].send(message.encode())
    sys.exit(0)

# Read a single line (ending with \n) from a socket and return it.
# We will strip out the \r and the \n in the process.

def get_line_from_socket(sock):
    done = False
    line = ''
    while (not done):
        char = sock.recv(1).decode('ISO-8859-1')
        if (char == '\r'):
            pass
        elif (char == '\n'):
            done = True
        else:
            line = line + char
    return line

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

def client_add(user, conn):
    registration = (user, conn)
    client_list.append(registration)
    user_name_list.append(user)
    at_user = ('@' + user)
    dict[user] = ['@all', at_user]
    print(f'dictionary after adding user: {dict}')
    
# Remove a client when disconnected.

def client_remove(user):
    for reg in client_list:
        if reg[0] == user:
            client_list.remove(reg)
            user_name_list.remove(reg[0])
            if reg[0] in dict:
                del dict[reg[0]]
                print(f'dictionary after removing user: {dict}')
            break

# Function to read messages from clients.

def read_message(sock, mask):
    message = get_line_from_socket(sock)

    # Does this indicate a closed connection?

    if message == '':
        print('Closing connection')
        sel.unregister(sock)
        sock.close()

    # Receive the message.  

    else:
        user = client_search_by_socket(sock)
        print(f'Received message from user {user}:  ' + message)
        words = message.split(' ')
        
        # Check for client disconnections.  
        if words[0] == 'DISCONNECT':
            print('Disconnecting user ' + user)
            client_remove(user)
            sel.unregister(sock)
            sock.close()
        
        
        # opperation to get list of all the users
        elif words[1] == ('!list'):
            string_list = ','.join(user_name_list)
            print("list result: " +string_list)            
            for reg in client_list:
                if reg[0] == user:
                    client_sock = reg[1]
                    forwarded_message = (f'{string_list}\n')
                    client_sock.send(forwarded_message.encode())
            
            
        # opperation to follow certain users
        elif words[1] == ('!follow'):
            if words[2] in dict[user]: # check if the term already exists for user
                print('error. term already being followed')
            else: # else, add the term to dictionary for user
                dict[user].append(words[2])
                forwarded_message = ('Now following ' + words[2] + '\n')
                print('Now following ' + words[2])
                
                # send a response to the user that followed
                for reg in client_list:
                    if reg[0] == user:
                        client_sock = reg[1]
                        client_sock.send(forwarded_message.encode())

        # opperation to unfollow the given term
        elif words[1] == ('!unfollow'):
            at_user = ('@' + user)
            if words[2] in dict[user] and words[2] != 'all' and words[2] != at_user: # check if term is in dict for user and not to unregister from itself
                dict[user].remove(words[2])
                forwarded_message = ('No longer following ' + words[2] + '\n')
                print('No longer following ' + words[2])
                
                for reg in client_list:# send a response to the user that followed
                    if reg[0] == user:
                        client_sock = reg[1]
                        client_sock.send(forwarded_message.encode())
                print(f'user: {user} unfollowed term: {words[2]}')
            else:
                print("error: not following term or cannot remove term")
            
        # opperation to show following list
        elif words[1] == ('!follow?'):
            
            # create a list of values that the user is following and convert to string
            string_list = []
            for value in dict[user]:
                print(value)
                string_list.append(value)
            string_list = ', '.join(string_list)
            print("list result: " +string_list)
                    
            for reg in client_list: # return message to user
                if reg[0] == user:
                    client_sock = reg[1]
                    forwarded_message = f'{string_list}\n'
                    client_sock.send(forwarded_message.encode())
            
            
        # opperation to disconnect from the server
        elif words[1] == ('!exit'):
            print('Disconnecting user ' + user)
            message='DISCONNECT CHAT/1.0\n'
            for reg in client_list:
                if reg[0] == user:
                    reg[1].send(message.encode())
            client_remove(user)
            sel.unregister(sock)
            sock.close()
            
            
        # opperation to send a local file in the format: !attach <filename> terms
        elif words[1] == ('!attach'):
            sock.setblocking(True)
            message_list= []
            try:
                stripped = message.replace(',', '').replace('.','').replace(':','').replace(';','').replace('!','').replace('?','')
                message_list= stripped.split(' ') # stripped terms
                
                file_name = words[2]
                msg = ('SEND '+ file_name +'\n')
                sock.send(msg.encode())
                file_specs = get_line_from_socket(sock).split(" ")
                
                # determine file information
                file_size = int(file_specs[0])
                size = int(file_specs[1])
                number_of_packets = int(file_specs[2])
                
                file_packets = ''           
                print(f'now receiving {file_name} packets from {user}')
                try:
                    for i in range(0, number_of_packets): # recieve
                        print(f'receiving packets...')
                        packet = sock.recv(size).decode()
                        file_packets = file_packets+ packet
                    print(f'{file_name}: finished recieving')
                except:
                    print('error receiving file')
                    
                # check each user
                for reg in client_list:
                    if reg[0] == user:# do not send to self
                        continue
                    
                    value_list = []
                    for value in dict[reg[0]]:
                        value_list.append(value)
                    
                    # if user is following the term, send the files
                    for term in value_list:
                        if term in message_list:
                            client_sock = reg[1]
                            
                            # sends to client so it can handle recieving the packets
                            client_sock.setblocking(True)
                            message = (f'RECEIVE {file_name} {user} {file_size} {size} {number_of_packets}\n')
                            client_sock.send(message.encode())
                            
                            # send packet to client
                            print(f'Now sending packets from {file_name} to user "{reg[0]}"')
                            data = file_packets
                            try:
                                while (data!= ''):
                                    print(f'sending packets...')
                                    data_packet = data[:size]
                                    client_sock.send(data_packet.encode())
                                    data = data[size:]
                            except:
                                print('error sending packets')
                                
                            print(f'{file_name} packet transfer to user "{reg[0]}" complete')
                            client_sock.setblocking(False)
            except:
                print('error with transfering file')
                pass
            sock.setblocking(False)
            
        
        # Send message to all users. Send at most only once, and don't send to yourself. 
        # Need to re-add stripped newlines here.
        else:
            message_list = []

            stripped = message.replace(',', '').replace('.','').replace(':','').replace(';','').replace('!','').replace('?','')
            message_list = stripped.split(' ')
            
            # for each connected user
            for reg in client_list:
                if reg[0] == user: # dont send to self
                    continue
                
                # creates a list of terms followed by the user
                value_list = []
                for value in dict[reg[0]]:
                    value_list.append(value)
                
                # iterates over the term for the user and if the term is in the users following list. send the message.
                for term in value_list:
                    if term in message_list:
                        client_sock = reg[1]
                        forwarded_message = f'{message}\n'
                        client_sock.send(forwarded_message.encode())
                        break
                    

# Function to accept and set up clients.

def accept_client(sock, mask):
    conn, addr = sock.accept()
    print('Accepted connection from client address:', addr)
    message = get_line_from_socket(conn)
    message_parts = message.split()

    # Check format of request.

    if ((len(message_parts) != 3) or (message_parts[0] != 'REGISTER') or (message_parts[2] != 'CHAT/1.0')):
        print('Error:  Invalid registration message.')
        print('Received: ' + message)
        print('Connection closing ...')
        response='400 Invalid registration\n'
        conn.send(response.encode())
        conn.close()

    # If request is properly formatted and user not already listed, go ahead with registration.

    else:
        user = message_parts[1]

        if (client_search(user) == None):
            client_add(user,conn)
            print(f'Connection to client established, waiting to receive messages from user \'{user}\'...')
            response='200 Registration succesful\n'
            conn.send(response.encode())
            conn.setblocking(False)
            sel.register(conn, selectors.EVENT_READ, read_message)

        # If user already in list, return a registration error.

        else:
            print('Error:  Client already registered.')
            print('Connection closing ...')
            response='401 Client already registered\n'
            conn.send(response.encode())
            conn.close()


# Our main function.

def main():

    # Register our signal handler for shutting down.

    signal.signal(signal.SIGINT, signal_handler)

    # Create the socket.  We will ask this to work on any interface and to pick
    # a free port at random.  We'll print this out for clients to use.

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('', 0))
    print('Will wait for client connections at port ' + str(server_socket.getsockname()[1]))
    server_socket.listen(100)
    server_socket.setblocking(False)
    sel.register(server_socket, selectors.EVENT_READ, accept_client)
    print('Waiting for incoming client connections ...')
     
    # Keep the server running forever, waiting for connections or messages.
    
    while(True):
        events = sel.select()
        for key, mask in events:
            callback = key.data
            callback(key.fileobj, mask)    

if __name__ == '__main__':
    main()
