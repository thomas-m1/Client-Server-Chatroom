# Client-Server-Chatroom
A Chatroom using TCP and UDP allowing multiple users to chat and send files/messages too each other.

2 versions. One using TCP and one with UDP

To run client for both UDP and TCP do: python3 client.py <username> chat://localhost:port

user is automatically subscribed to itself and @all
some commands:
  !list -> List of all the users in the chatroom
  !follow <term> -> follows a term
  !follow? -> follow list of the terms a user is following
  !attach <file> <term> -> sends a file to the users following the term
  !exit -> exits the application
