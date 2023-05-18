#Python3
from socket import *
import os.path

serverPort = 8000

serverSocket = socket(AF_INET, SOCK_STREAM)

serverSocket.bind(('localhost', serverPort))

serverSocket.listen(1)

print ("The server is ready to receive")

while True:
    connectionSocket, addr = serverSocket.accept()    
    # get request 
    request = connectionSocket.recv(1024).decode('utf-8')
    request_list = request.split(" ")
    request_path = request_list[1]
    request_file = request_path.strip('/')

    if not os.path.isfile(request_file):
        response_line = "HTTP/1.1 404 Not Found\r\n"
        connectionSocket.send(response_line.encode("utf-8"))

    if (request_file == "index.html"):
        with open(request_file, "rb") as file:
            file_data = file.read()
        response_line = "HTTP/1.1 200 OK\r\n"
        response_header = "Content-Type: text/html\r\n"
        response_body = file_data
        response = (response_line +
                        response_header +
                        "\r\n").encode("utf-8") + response_body
        connectionSocket.send(response)

    elif(request_file == "myimage.png"):
        with open(request_file, "rb") as file:
            file_data = file.read()
        response_line = "HTTP/1.1 200 OK\r\n"
        response_header = "Content-Type: image/png\r\n"
        response_body = file_data
        response = (response_line +
                        response_header +
                        "\r\n").encode("utf-8") + response_body
        connectionSocket.send(response)

    connectionSocket.close()
