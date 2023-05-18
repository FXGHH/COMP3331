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
from header_type import Htype, get_type  # a class contain all segment header type


BUFFERSIZE = 1024

# max time to resend segment
MAX_RETRY = 3

CLOSED = 0
SYN_SENT = 1
ESTABLISHED = 2
CLOSING = 3
FIN_WAIT = 4


class Data_Segment:
    def __init__(self, index, seqno, data, expected_seqno, acked=False, last_send_time=0):
        self.index = index
        self.seqno = seqno
        self.data = data
        self.expected_seqno = expected_seqno
        self.acked = acked
        self.last_send_time = last_send_time


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
        self.max_win = int(max_win) // 1000
        self.rot = int(rot)
        self.windows = []  # type: list[Data_Segment]
        # at start the sender is in closed state
        self.state = CLOSED
        # get a random sequence number between 1 to 2^16 - 1 and mod 2^16
        self.start_seqno = random.randint(1, 2 ** 16 - 1)
        self.expected_ack_seqno_for_syn = (self.start_seqno + 1) % 2 ** 16

        # init the UDP socket
        self.sender_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self.sender_socket.bind(self.sender_address)

        self._is_active = True  # for the multi-threading

        self.start_time = 0
        # current segment time we observing
        self.curr_packet_time = 0
        # count the number of data segment we have
        self.i = 0
        # the send retry time
        self.retry_times = 0

        self.syn_retry = 0
        self.fin_retry = 0
        self.base = 0
        # check if all packet has been acked
        self.all_packets_acked = False
        self.synced = False
        self.data_acked = False
        self.fined = False
        self.listen_thread = Thread(target=self.listen)
        # self.listen_thread.
        self.listen_thread.start()

        self.syn_timer = Thread(target=self.syn_timeout)
        self.fin_timer = Thread(target=self.fin_timeout)

        self.data_timer = None
        # contain all the splited data we need send
        self.data_segments = []
        self.seqno_for_fin_wait = 0
        self.expected_ack_seqno_for_fin = 0
        self.read_input_file()

        self.dss = 0  # Number of Data Segments Sent
        self.dtb = 0  # Amount of (original) Data Transferred
        self.rds = 0  # Number of Retransmitted Data Segments
        self.rda = 0  # 'Number of Duplicate Acknowledgements received
        pass
    
    #split the input file as suitable data segment and store it
    def read_input_file(self):
        with open(self.filename, 'r') as f:
            content = f.read().encode('utf-8')
        seqno = (self.start_seqno + 1) % 2 ** 16
        expected_seqno = 0
        for i in range(0, len(content), 1000):
            data = content[i:i + 1000]
            expected_seqno = (seqno + len(data)) % 2 ** 16
            data_segment = Data_Segment(i, seqno, data, expected_seqno, False, 0)
            self.data_segments.append(data_segment)
            seqno = expected_seqno
        self.seqno_for_fin_wait = expected_seqno
        self.expected_ack_seqno_for_fin = (expected_seqno + 1) % 2 ** 16
    
    # check if syn segment already timeout
    def syn_timeout(self):
        while self._is_active and self.state == SYN_SENT:
            while time.time() - self.curr_packet_time < self.rot / 1000:
                if self.state != SYN_SENT or self.synced:
                    return
                continue
            # if we still can't receive the syn ack then we will send reset segment
            if self.synced is False:
                if self.syn_retry >= MAX_RETRY:
                    self._is_active = False
                    self.state = CLOSED
                    seqno = 0
                    self.write_log('snd', Htype.RESET, seqno, 0)
                    headers = Htype.RESET.to_bytes(2, 'big') + seqno.to_bytes(2, 'big')
                    self.sender_socket.sendto(headers, self.receiver_address)
                    return
                else:
                    # try to resend asain
                    self.syn_retry += 1
                    self.write_log('snd', Htype.SYN, self.start_seqno, 0)
                    headers = Htype.SYN.to_bytes(2, 'big') + self.start_seqno.to_bytes(2, 'big')
                    self.sender_socket.sendto(headers, self.receiver_address)
                    self.curr_packet_time = time.time()
    
    # check if fin segment already timeout
    def fin_timeout(self):
        while self._is_active and self.state == FIN_WAIT:
            while time.time() - self.curr_packet_time < self.rot / 1000:
                if self.fined:
                    return
                continue
            # if we still can't receive the fin ack then we will send reset segment
            if not self.fined:
                if self.fin_retry >= MAX_RETRY:
                    self._is_active = False
                    self.state = CLOSED
                    seqno = 0
                    self.write_log('snd', Htype.RESET, seqno, 0)
                    headers = Htype.RESET.to_bytes(2, 'big') + seqno.to_bytes(2, 'big')
                    self.sender_socket.sendto(headers, self.receiver_address)
                    return
                else:
                    # try to resend asain
                    self.fin_retry += 1

                    self.write_log('snd', Htype.FIN, self.seqno_for_fin_wait, 0)
                    headers = Htype.FIN.to_bytes(2, 'big') + self.seqno_for_fin_wait.to_bytes(2, 'big')
                    self.sender_socket.sendto(headers, self.receiver_address)
                    self.curr_packet_time = time.time()

    def get_first_non_acked_in_windows(self):
        for data_segment in self.windows:
            if data_segment.acked is False:
                return data_segment
        return None
    
    # check does the oldest unack segment already timeout
    def data_timeout(self):
        while self._is_active and self.state in [ESTABLISHED, CLOSING]:

            data_segment = self.get_first_non_acked_in_windows()
            if data_segment is None:
                continue

            last_send_time = data_segment.last_send_time
            sleeped_time = 0 if time.time() - last_send_time >= self.rot / 1000 else self.rot / 1000 - (time.time() - last_send_time)
            time.sleep(sleeped_time)
            # if we can't get that segment ack we will send the segment again
            if data_segment.acked is False:
                data_segment.last_send_time = time.time()
                self.rds += 1
                self.write_log('snd', Htype.DATA, data_segment.seqno, len(data_segment.data))
                header = Htype.DATA.to_bytes(2, 'big') + data_segment.seqno.to_bytes(2, 'big')
                content = header + data_segment.data
                data_segment.last_send_time = time.time()
                self.sender_socket.sendto(content, self.receiver_address)

    def ptp_open(self):
        self.start_time = datetime.datetime.timestamp(datetime.datetime.now())
        self.send_syn()
        self.syn_timer.start()
    
    # get the except segment from the window
    def get_index_in_windows(self, expected_seqno):
        for i in range(len(self.windows)):
            if self.windows[i].expected_seqno == expected_seqno:
                return i
        return -1

    def ptp_send(self):
        # do the while loop until we establish with receiver
        while self.state != ESTABLISHED:
            if self.state == CLOSED:
                return
            continue
        self.data_acked = self.synced
        # send every segment from our pre data segmentss
        while self.i < len(self.data_segments):
            #send every segments in our window(unsend)
            while len(self.windows) < self.max_win:
                if self.i < len(self.data_segments):
                    data_segment = self.data_segments[self.i]
                    self.i += 1
                    self.windows.append(data_segment)
                    header = Htype.DATA.to_bytes(2, 'big') + data_segment.seqno.to_bytes(2, 'big')
                    content = header + data_segment.data
                    # set the time we sent it
                    data_segment.last_send_time = time.time()
                    self.write_log('snd', Htype.DATA, data_segment.seqno, len(data_segment.data))
                    self.sender_socket.sendto(content, self.receiver_address)
                    self.dtb += len(data_segment.data)
                    self.dss += 1
                    if self.data_timer is None:
                        self.data_timer = Thread(target=self.data_timeout)
                        self.data_timer.start()
                    if self.i == len(self.data_segments):
                        self.state = CLOSING
                        return

    def ptp_close(self):
        # while loop stop until we send fin segment
        while self.state != FIN_WAIT and self.state != CLOSED:
            continue
        if self.state == FIN_WAIT:
            self.fined = False
            self.write_log('snd', Htype.FIN, self.seqno_for_fin_wait, 0)
            header = Htype.FIN.to_bytes(2, 'big') + self.seqno_for_fin_wait.to_bytes(2, 'big')
            self.sender_socket.sendto(header, self.receiver_address)
            self.retry_times = 0
            self.curr_packet_time = time.time()

            self.fin_timer.start()
            time.sleep(5)
            self._is_active = False
            self.sender_socket.close()
            logging.info(f'Amount of (original) Data Transferred {self.dtb}')
            logging.info(f'Number of Data Segments Sent {self.dss}')
            logging.info(f'Number of Retransmitted Data Segments {self.rds}')
            logging.info(f'Number of Duplicate Acknowledgements received {self.rda}')
        elif self.state == CLOSED:
            time.sleep(5)
            self.sender_socket.close()

    def listen(self):

        # the current sender state is active and syn segment already sent
        while self._is_active:
            try:
                incoming_message, receiver_address = self.sender_socket.recvfrom(BUFFERSIZE)
            except:
                break
            seqno = int.from_bytes(incoming_message[2:4], byteorder='big')
            header_type = int.from_bytes(incoming_message[0:2], byteorder='big')
            self.write_log('rcv', header_type, seqno, len(incoming_message[4:]))
            # check if we receive correct syn segment
            if seqno == self.expected_ack_seqno_for_syn:
                if self.state == SYN_SENT:
                    self.state = ESTABLISHED
                    self.synced = True
                else:
                    self.rda += 1

             # check if we receive correct fin segment
            elif seqno == self.expected_ack_seqno_for_fin:
                if self.state == FIN_WAIT:
                    self.state = CLOSED
                    self._is_active = False
                    self.fined = True
                else:
                    self.rda += 1
            else:
                # check if we receive data segment
                index_in_windows = self.get_index_in_windows(seqno)
                if index_in_windows == -1:
                    self.rda += 1
                else:
                    # update the segment state if we receive thhe data segment ack
                    if self.windows[index_in_windows].acked is False:
                        self.windows[index_in_windows].acked = True
                    else:
                        self.rda += 1
                    while True:
                        # we finish send all data segments
                        if len(self.windows) == 0:
                            if self.state == CLOSING:
                                self.state = FIN_WAIT
                            break
                        if self.windows[0].acked is False:
                            break
                        del self.windows[0]

    def send_syn(self):
        self.state = SYN_SENT
        header_type = Htype.SYN
        header = header_type.to_bytes(2, 'big') + self.start_seqno.to_bytes(2, 'big')
        self.write_log("snd", Htype.SYN, self.start_seqno, 0)
        self.sender_socket.sendto(header, self.receiver_address)
        # set current syn segment send time
        self.curr_packet_time = time.time()

    def run(self):
        '''
        This function contain the main logic of the receiver
        '''

        self.ptp_open()
        self.ptp_send()
        self.ptp_close()

    def write_log(self, action, packet_type, seqno, size):
        packet_type = get_type(packet_type)
        current_time = datetime.datetime.timestamp(datetime.datetime.now())
        interval = (current_time - self.start_time) * 1000
        log = '{:<8}\t{:<10.2f}\t{:<8}\t{:<8}\t{:<8}'.format(action, interval, packet_type, str(seqno), str(size))
        logging.info(log)


if __name__ == '__main__':
    # logging is useful for the log part: https://docs.python.org/3/library/logging.html
    logging.basicConfig(
        filename="Sender_log.txt",
        level=logging.INFO,
        format='',
        filemode='w')

    if len(sys.argv) != 6:
        print(
            "\n===== Error usage, python3 sender.py sender_port receiver_port FileReceived.txt max_win rot ======\n")
        exit(0)

    sender = Sender(*sys.argv[1:])
    sender.run()
