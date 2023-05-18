# python3 
import socket      
import time      

HOST_IP = '127.0.0.1'
HOST_PORT = 8000    


address = (HOST_IP, HOST_PORT)    
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

s.settimeout(1)
response = []

for i in range(1, 16):
    message = "PING {} {} \r\n".format(i, time)
    sendTime = time.time()
    s.sendto(message.encode(), address)
    rtt = 0

    try:
        s.recv(1024)
        backTime = time.time()
        rtt = int((backTime - sendTime) * 1000)
        print ("ping to 127.0.0.1, seq = %d, rtt = %d ms" % (i, rtt))
        response.append(rtt)

    except socket.timeout:
        print ("ping to 127.0.0.1, seq = %d, time out" % (i))
    continue

print("min rtt: %d, max rtt: %d, average rtt: %d" % (min(response), 
                                                    max(response), 
                                                    sum(response)/len(response)))






