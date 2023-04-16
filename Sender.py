"""
    Sample code for Sender (multi-threading)
    Python 3
    Usage: python3 sender.py receiver_port sender_port FileToSend.txt max_recv_win rto
    coding: utf-8

    Notes:
        Try to run the server first with the command:
            python3 receiver.py 9000 10000 FileReceived.txt 1 1
        Then run the sender:
            python3 sender.py 11000 9000 FileToReceived.txt 1000 1

    Author: Rui Li (Tutor for COMP3331/9331)
"""
# here are the libs you may find it useful:
import datetime, time
import threading
import signal
import random  # to calculate the time delta of packet transmission
import logging, sys  # to write the log
import socket  # Core lib, to send packet via UDP socket
from threading import Thread  # (Optional)threading will make the timer easily implemented
from header_type import Htype # a class contain all segment header type


BUFFERSIZE = 1024

# max time to resend segment
MAX_RETRY = 3

CLOSED = 0
SYN_SENT = 1
ESTABLISHED = 2
CLOSING = 3
FIN_WAIT = 4

timed_out = False

class Sender:
    def __init__(self, sender_port: int, receiver_port: int, filename: str, max_win: int, rot: int) -> None:
        '''
        The Sender will be able to connect the Receiver via UDP
        :param sender_port: the UDP port number to be used by the sender to send PTP segments to the receiver
        :param receiver_port: the UDP port number on which receiver is expecting to receive PTP segments from the sender
        :param filename: the name of the text file that must be transferred from sender to receiver using your reliable transport protocol.
        :param max_win: the maximum window size in bytes for the sender window.
        :param rot: the value of the retransmission timer in milliseconds. This should be an unsigned integer.
        '''
        self.sender_port = int(sender_port)
        self.receiver_port = int(receiver_port)
        self.sender_address = ("127.0.0.1", self.sender_port)
        self.receiver_address = ("127.0.0.1", self.receiver_port)

        self.filename = filename
        self.max_win = int(max_win)
        self.rot = int(rot)

        # at start the sender is in closed state
        self.state = CLOSED
        # get a random sequence number between 1 to 2^16 - 1 and mod 2^16
        self.seqno = random.randint(1, 2**16 - 1)


        # self.packets_dic = {}
        # self.initialize_packet_dic()

        # init the UDP socket
        logging.debug(f"The sender is using the address {self.sender_address}")
        self.sender_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self.sender_socket.bind(self.sender_address)
        
        #  (Optional) start the listening sub-thread first
        self._is_active = True  # for the multi-threading

        self.listen_thread = Thread(target = self.listen)
        self.listen_thread.start()
        # self.syn_listen_thread = Thread(target = self.syn_listen)
        # syn_listen_thread.start()
        self.start_time = 0

        #create a sender side log file
        # self.log_file = open('Sender_log.txt', 'a+')
        self.log_file_name = 'Sender_log.txt'

        self.i = 0

        self.packets = []

        #conatin all the packet's sequence and data segment

        # check if all packet has been acked
        self.all_packets_acked  = False


        # todo add codes here
        pass

    def ptp_open(self):
        # self.sender_socket.sendto(message.encode("utf-8"), self.receiver_address)
        # header_type = Htype.SYN
        # header = header_type.to_bytes(2, 'big') + self.seqno.to_bytes(2, 'big')
        # self.sender_socket.sendto(header, self.receiver_address)
        # self.initialize_packet_dic()\

        # self.syn_listen_thread.start()
        self.send_syn()
        #set the start send syn segment time
        # now = datetime.datetime.now()
        # self.start_time = datetime.datetime.timestamp(datetime.datetime.now())
        # snd 0 SYN 4521 0
        self.write_log("snd", "SYN", self.seqno, 0)
        # self.start_time = time.time()
        # time.sleep(self.rot / 1000)
        self.sender_socket.settimeout(self.rot / 1000)
    
    def initialize_packet_dic(self):
        original_seqno = self.seqno
        # assume we after we got syn ack
        self.seqno += 1
        with open(self.filename, mode='rb') as file:
                i = 0
                while True:
                    payload = file.read(1000)
                    if payload:
                        header_type = Htype.DATA
                        header = header_type.to_bytes(2, 'big') + self.seqno.to_bytes(2, 'big')
                        # header = header_type + self.seqno

                        self.seqno = (self.seqno + len(payload)) % 2**16 
                            
                        content = header + payload
                        self.packets_dic[i] = content
                        i += 1
                    else:
                        logging.debug(f'All {i} packets have been processed')
                        self.seqno = original_seqno
                        break

    # def unpack_dic_packet(self, content):
    #        incoming_message = content
    #        header_type = int.from_bytes(incoming_message[0:2], byteorder='big')
    #        seqno = int.from_bytes(incoming_message[2:4], byteorder='big')
    #        payload = 


    def ptp_send(self):
        # todo add codes here
        if self.state == ESTABLISHED:
            # for key, value in self.packets_dic:
            #     incoming_message = 
            #     header_type = int.from_bytes(incoming_message[0:2], byteorder='big')
            #     seqno = int.from_bytes(incoming_message[2:4], byteorder='big')
            #     print(key, value)
            with open(self.filename, mode='rb') as file:
                while True:
                    payload = file.read(1000)
                    if payload:
                        header_type = Htype.DATA
                        header = header_type.to_bytes(2, 'big') + self.seqno.to_bytes(2, 'big')
                        content = header + payload
                        self.packets.append(content)

                        self.sender_socket.sendto(content, self.receiver_address)

                        self.write_log("snd", "DATA", self.seqno, len(payload))

                        # self.seqno += len(content)
                        # if self.seqno + len(content) >= (2**16 - 1):
                        #     # sequence number go back to 0 after reach the number limit
                        #     self.seqno = 0
                        # else:
                        #     self.seqno += len(content)
                        self.seqno = (self.seqno + len(payload)) % 2**16 

                        # logging.debug(f"Packet {i}: {len(packet)} bytes")
                        self.i += 1
                    else:
                        logging.debug(f'All {self.i} packets have been processed')
                        # self.ptp_close()
                        break
            pass

    
    def set_timeout(self):
        global timed_out
        timed_out = True

    def retransmit(self):
        pass

    def ptp_close(self):
        # todo add codes here
        # print(self.packets_dic[0])
        time.sleep(3)
        self.state = CLOSED
        self._is_active = False  # close the sub-thread
        logging.info(f"Notice this ptp will cloed!!!!!!!!!!")
        pass
    


    def listen(self):
        '''(Multithread is used)listen the response from receiver'''
        logging.debug("Sub-thread for listening is running")
        # self.syn_listen_thread.start()
        retry = 0
        # if self._is_active == True:
        #     print("false now")
        while self._is_active:
            
            # if self.state == SYN_SENT:
            #     # logging.debug("cccccccccccccccccc")
            #     if retry >= MAX_RETRY:
            #         # logging.debug("reach maxxxxxx")
            #         self.ptp_close()
            #         break
            try:
                incoming_message, _ = self.sender_socket.recvfrom(BUFFERSIZE)
                seqno = int.from_bytes(incoming_message[2:4], byteorder='big')

                if self.state == SYN_SENT:
                # logging.debug("cccccccccccccccccc")
                    if retry >= MAX_RETRY:
                        logging.debug("reach maxxxxxx")
                        self.ptp_close()
                        break
                # check if we get correct syn ack 
                    if (self.seqno + 1) == seqno:
                        self.seqno += 1
                        #write syn ack in log file
                        self.write_log("rcv", "ACK", self.seqno, 0)
                        self.state = ESTABLISHED
                        logging.info("sender : connection built")
                        # self.listen_thread.start()
                        self.ptp_send()
                        continue
                if self.state == ESTABLISHED:
                        # logging.info("ACK expected is " + str(self.seqno + len(self.packets[self.i][4:])) + " | ACK received was " + str(seqno))
                        # if (self.seqno + len(self.packets[self.i][4:])):
                        #     self.seqno += len(self.packets[self.i][4:])
                        #     if self.i == len(self.packets) - 1:
                        #         self._is_active = False
                        #     self.i += 1


                        self.write_log("rcv", "DATA", self.seqno, 0)
                        
                elif self.state == CLOSING:
                    pass

                elif self.state == FIN_WAIT:
                    pass

                elif self.state == CLOSED:
                    pass

                else:
                    print("listen else condidtion happend!!!!!!!!!!!")

            except socket.timeout:
                if self.state == ESTABLISHED:
                    continue
                elif self.state == SYN_SENT:
                    logging.debug(f"dddddddddddddddddd{retry}")
                    logging.info(f"{retry} retry syn segment process")
                    logging.info(f"resend syn segment")
                    self.send_syn()
                    retry += 1
                    continue

            # incoming_message, _ = self.sender_socket.recvfrom(BUFFERSIZE)
            # header_type = int.from_bytes(incoming_message[0:2], byteorder='big')
            # seqno = int.from_bytes(incoming_message[2:4], byteorder='big')
            # logging.info(f"received data segement")

            # if self.state == ESTABLISHED:
            #         logging.info("ACK expected is " + str(self.seqno + len(self.packets[self.i][4:])) + " | ACK received was " + str(seqno))
            #         # if (self.seqno + len(self.packets[self.i][4:])):
            #         #     self.seqno += len(self.packets[self.i][4:])
            #         #     if self.i == len(self.packets) - 1:
            #         #         self._is_active = False
            #         #     self.i += 1

            #         self.write_log("rcv", "DATA", self.seqno, 0)
                    
            # elif self.state == CLOSING:
            #     pass

            # elif self.state == FIN_WAIT:
            #     pass

            # elif self.state == CLOSED:
            #     pass

            # else:
            #     print("listen else condidtion happend!!!!!!!!!!!")

        #get header type and sequence number
        
        # if it's a ack segment
        # if header_type == Htype.ACK:
        #     if self.state == SYN_SENT:
        #         self.build_connection(seqno)
        #     elif self.state == ESTABLISHED:
        #         self.established(self, seqno)
        # logging.info(f"received reply from receiver:, {incoming_message}")

    def send_syn(self):
        header_type = Htype.SYN
        header = header_type.to_bytes(2, 'big') + self.seqno.to_bytes(2, 'big')
        self.sender_socket.sendto(header, self.receiver_address)
        # self.sender_socket.settimeout(self.rot / 1000)
        # time.sleep(self.rot / 1000)
        self.state = SYN_SENT

    def send_reset(self):
        header_type = Htype.RESET
        header = header_type.to_bytes(2, 'big') + self.seqno.to_bytes(2, 'big')
        self.sender_socket.sendto(header, self.receiver_address)
        # after send the reset segment the sender will change to closed state
        self.state = CLOSED
    
    # the sender listen if it can receive the syn segement
    # def syn_listen(self):
    #     retry = 0
    #     while self._is_active:
    #         # logging.debug("bbbbbbbbbbbbbbbb")
    #         if self.state == SYN_SENT:
    #             # logging.debug("cccccccccccccccccc")
    #             if retry >= MAX_RETRY:
    #                 # logging.debug("reach maxxxxxx")
    #                 self.ptp_close()
    #                 break
    #             try:
    #                 incoming_message, _ = self.sender_socket.recvfrom(BUFFERSIZE)
    #                 seqno = int.from_bytes(incoming_message[2:4], byteorder='big')
    #                 # check if we get correct syn ack 
    #                 if (self.seqno + 1) == seqno:
    #                     self.seqno += 1
    #                     #write syn ack in log file
    #                     self.write_log("rcv", "ACK", self.seqno, 0)
    #                     self.state = ESTABLISHED
    #                     logging.info("sender : connection built")

    #                     # self.listen_thread.start()
    #                     self.ptp_send()
    #             except socket.timeout:
    #                 # logging.debug(f"dddddddddddddddddd{retry}")
    #                 logging.info(f"{retry} retry syn segment process")
    #                 logging.info(f"resend syn segment")
    #                 self.send_syn()
    #                 retry += 1
    #                 continue



    # def build_connection(self, seqno):
    #     logging.info("ACK expected is " + str(self.seqno + 1) + " | ACK received was " + str(seqno))
    #     if (self.seqno + 1) == seqno:
    #         self.seqno += 1
    #         # self.synced = True
    #         self.state = ESTABLISHED
    #     logging.info("sender : connection built")

    def established(self, seqno):
        logging.info("ACK expected is " + str(self.seqno + len(self.packets[self.i][4:])) + " | ACK received was " + str(seqno))
        if (self.seqno + len(self.packets[self.i][4:])):
            self.seqno += len(self.packets[self.i][4:])
            if self.i == len(self.packets) - 1:
                self._is_active = False
            self.i += 1
        pass

    def rec_reset(self):
        pass


    def run(self):
        '''
        This function contain the main logic of the receiver
        '''
        # todo add/modify codes here
        
        # self.syn_listen()
        # print("sssssssssssssssss")
        self.ptp_open()
        # self.syn_listen()
        # self.ptp_send()
        self.ptp_close()

    def write_log(self, action, packet_type, seqno, size):
        with open(self.log_file_name, 'a+') as file:
            # current_time = time.time()
            if packet_type == "SYN":
                self.start_time = datetime.datetime.timestamp(datetime.datetime.now())
            
            current_time = datetime.datetime.timestamp(datetime.datetime.now())
            # interval = '{:.2f}'.format((current_time - self.start_time) * 1000)

            interval = (current_time - self.start_time) * 1000
            # number_of_bytes = len(contents)
            log = '{:<8} {:<10.2f} {:<8} {:<8} {:<8}\n'.format(action, interval, packet_type, str(seqno), str(size))
            # log = action + '\t\t' + interval + '\t\t' + packet_type + '\t\t' + str(seqno) + \
            #     '\t\t' + str(size) + '\n'
            # log_txt.write(log)
            
            file.write(log)


if __name__ == '__main__':
    # logging is useful for the log part: https://docs.python.org/3/library/logging.html
    logging.basicConfig(
        # filename="Sender_log.txt",
        stream=sys.stderr,
        level=logging.DEBUG,
        format='%(asctime)s,%(msecs)03d %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d:%H:%M:%S')

    if len(sys.argv) != 6:
        print(
            "\n===== Error usage, python3 sender.py sender_port receiver_port FileReceived.txt max_win rot ======\n")
        exit(0)

    sender = Sender(*sys.argv[1:])
    sender.run()
