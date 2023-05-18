"""
    Sample code for Receiver
    Python 3
    Usage: python3 receiver.py receiver_port sender_port FileReceived.txt flp rlp
    coding: utf-8

    Notes:
        Try to run the server first with the command:
            python3 receiver.py 9000 10000 FileReceived.txt 1 1
        Then run the sender:
            python3 sender.py 11000 9000 FileToReceived.txt 1000 1

    Author: Rui Li (Tutor for COMP3331/9331)
"""
# here are the libs you may find it useful:
import datetime, time  # to calculate the time delta of packet transmission
import logging, sys  # to write the log
import socket  # Core lib, to send packet via UDP socket
from threading import Thread  # (Optional)threading will make the timer easily implemented
import random  # for flp and rlp function
from header_type import Htype, get_type  # a class contain all segment header type

BUFFERSIZE = 16 * 1024

CLOSED = 0
LISTEN = 1
ESTABLISHED = 2
TIME_WAIT = 3


class Receiver:
    def __init__(self, receiver_port: int, sender_port: int, filename: str, flp: float, rlp: float) -> None:
        '''
        The server will be able to receive the file from the sender via UDP
        :param receiver_port: the UDP port number to be used by the receiver to receive PTP segments from the sender.
        :param sender_port: the UDP port number to be used by the sender to send PTP segments to the receiver.
        :param filename: the name of the text file into which the text sent by the sender should be stored
        :param flp: forward loss probability, which is the probability that any segment in the forward direction (Data, FIN, SYN) is lost.
        :param rlp: reverse loss probability, which is the probability of a segment in the reverse direction (i.e., ACKs) being lost.

        '''
        self.address = "127.0.0.1"  # change it to 0.0.0.0 or public ipv4 address if want to test it between different computers
        self.receiver_port = int(receiver_port)
        self.sender_port = int(sender_port)
        self.server_address = (self.address, self.receiver_port)

        self.filename = filename
        self.flp = float(flp)
        self.rlp = float(rlp)
        # at start the receiver is in closed state
        self.state = CLOSED
        self.seqs_saved = []
        # init the UDP socket
        # define socket for the server side and bind address

        self.receiver_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self.receiver_socket.bind(self.server_address)
        self.received_windows = []
        self.start_window_seq = 0
        self.orderd_data = []
        # create a receiver side log file
        self.start_time = -1
        self.seqno = 0
        self.org_seqno = 0
        self.rdb = 0  # Amount of (original) Data Received
        self.rds = 0  # Number of (original) Data Segments Received
        self.rdds = 0  # Number of duplicate Data segments received
        self.dds = 0  # Number of Data segments dropped
        self.das = 0  # Number of ACK segments dropped
        self.fined=False
        pass

    def get_position_in_window(self, seqno):
        if seqno >= self.start_window_seq:
            return (seqno - self.start_window_seq) // 1000
        else:
            return (seqno + 2 ** 16 - self.start_window_seq) // 1000

    def run(self) -> None:
        '''
        This function contain the main logic of the receiver
        '''
        # create the receive file
        with open(self.filename, 'w') as f:
            pass
        self.state = LISTEN
        while True:

            try:
                incoming_message, sender_address = self.receiver_socket.recvfrom(BUFFERSIZE)
                seqno = int.from_bytes(incoming_message[2:4], byteorder='big')
                header_type = int.from_bytes(incoming_message[0:2], byteorder='big')
                # randomly drop the packet we received 
                if random.random() < self.flp and header_type != Htype.RESET:
                    self.write_log('drp', header_type, seqno, len(incoming_message[4:]))
                    if header_type == Htype.DATA:
                        self.dds += 1
                    continue
                # if we receive the syn segment
                if header_type == Htype.SYN:
                    seqno_for_ack = (seqno + 1) % (2 ** 16)
                    if self.state == LISTEN:
                        self.state = ESTABLISHED
                        self.write_log('rcv', header_type, seqno, 0)
                        self.start_time = datetime.datetime.timestamp(datetime.datetime.now())
                        self.start_window_seq = seqno_for_ack
                        # random drop the segemnt
                        if random.random() < self.rlp:
                            self.write_log('drp', Htype.ACK, seqno_for_ack, 0)
                            self.das += 1
                        else:
                            # if we receive the segemnt
                            self.write_log('snd', Htype.ACK, seqno_for_ack, 0)
                            headers = Htype.ACK.to_bytes(2, 'big') + seqno_for_ack.to_bytes(2, 'big')
                            self.receiver_socket.sendto(headers, sender_address)
                    else:
                        # prevent if we receive duplicate syn segment
                        self.write_log('rcv', header_type, seqno, 0)
                        if random.random() < self.rlp:
                            self.write_log('drp', Htype.ACK, seqno_for_ack, 0)
                            self.das += 1
                        else:
                            self.write_log('snd', Htype.ACK, seqno_for_ack, 0)
                            headers = Htype.ACK.to_bytes(2, 'big') + seqno_for_ack.to_bytes(2, 'big')
                            self.receiver_socket.sendto(headers, sender_address)

                # if we receive the data segment
                elif header_type == Htype.DATA:
                    data = incoming_message[4:]
                    seqno_for_ack = (seqno + len(data)) % 2 ** 16
                    self.write_log("rcv", header_type, seqno, len(data))
                    self.rds += 1
                    # if we receive the duplicate data segment 
                    if seqno in self.seqs_saved:
                        self.rdds += 1
                        if random.random() < self.rlp:
                            self.write_log('drp', Htype.ACK, seqno_for_ack, 0)
                            self.das += 1
                        else:
                            self.write_log('snd', Htype.ACK, seqno_for_ack, 0)
                            headers = Htype.ACK.to_bytes(2, 'big') + seqno_for_ack.to_bytes(2, 'big')
                            self.receiver_socket.sendto(headers, sender_address)
                    else:
                        # if the data segemnt is new 
                        self.rdb += len(data)
                        index = self.get_position_in_window(seqno)
                        if len(self.received_windows) <= index:
                            # update the window size 
                            self.received_windows.extend([None for _ in range(index + 1 - len(self.received_windows))])
                        self.received_windows[index] = data
                        # initialize window and ready to manage data segment
                        if index == 0:
                            while True:
                                if len(self.received_windows) == 0:
                                    break
                                if self.received_windows[0] is None:
                                    break
                                data = self.received_windows[0]
                                self.seqs_saved.append(self.start_window_seq)
                                self.orderd_data.append(data)
                                self.start_window_seq = (self.start_window_seq + len(data)) % 2 ** 16
                                del self.received_windows[0]
                        if random.random() < self.rlp:
                            self.write_log('drp', Htype.ACK, seqno_for_ack, 0)
                            self.das += 1
                        else:
                            self.write_log('snd', Htype.ACK, seqno_for_ack, 0)
                            headers = Htype.ACK.to_bytes(2, 'big') + seqno_for_ack.to_bytes(2, 'big')
                            self.receiver_socket.sendto(headers, sender_address)
                
                # if we receive fin segement
                elif header_type == Htype.FIN:
                    self.write_log("rcv", Htype.FIN, seqno, 0)
                    seqno_for_ack = (seqno + 1) % 2 ** 16

                    if random.random() < self.rlp:
                        self.write_log('drp', Htype.ACK, seqno_for_ack, 0)
                        self.das += 1
                    else:
                        self.write_log('snd', Htype.ACK,seqno_for_ack, 0)
                        headers = Htype.ACK.to_bytes(2, 'big') + seqno_for_ack.to_bytes(2, 'big')
                        self.receiver_socket.sendto(headers, sender_address)
                        logging.info(f'Amount of (original) Data Received {self.rdb}')
                        logging.info(f'Number of (original) Data Segments Received {self.rds}')
                        logging.info(f'Number of duplicate Data segments received {self.rdds}')
                        logging.info(f'Number of Data segments dropped {self.dds}')
                        logging.info(f'Number of ACK segments dropped {self.das}')
                        self.save_file()
                        return

                elif header_type == Htype.RESET:
                    self.write_log("rcv", Htype.RESET, seqno, 0)
                    print('a closure of the connection due to a RESET packet')
                    return

            except ConnectionResetError:
                print(1)
                break

    def save_file(self):
        with open(self.filename, 'wb') as f:
            for data in self.orderd_data:
                f.write(data)

    def write_log(self, action, packet_type, seqno, size):
        packet_type = get_type(packet_type)

        if packet_type == "SYN" and action == 'rcv' and self.start_time == -1:
            self.start_time = datetime.datetime.timestamp(datetime.datetime.now())
        current_time = datetime.datetime.timestamp(datetime.datetime.now())
        interval = (current_time - self.start_time) * 1000 if self.start_time!=-1 else 0
        log = '{:<8}\t{:<10.2f}\t{:<8}\t{:<8}\t{:<8}'.format(action, interval, packet_type, str(seqno), str(size))
        logging.info(log)


if __name__ == '__main__':
    # logging is useful for the log part: https://docs.python.org/3/library/logging.html
    logging.basicConfig(
        filename="Receiver_log.txt",
        level=logging.INFO,
        format='',
        filemode='w')

    if len(sys.argv) != 6:
        print(
            "\n===== Error usage, python3 receiver.py receiver_port sender_port FileReceived.txt flp rlp ======\n")
        exit(0)

    receiver = Receiver(*sys.argv[1:])
    receiver.run()
