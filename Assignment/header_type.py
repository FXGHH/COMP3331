# Class header type contain all type the segment
def get_type(which):
    types = ['DATA', 'ACK', 'SYN', 'FIN', 'RESET']
    return types[which]


class Htype:
    DATA = 0
    ACK = 1
    SYN = 2
    FIN = 3
    RESET = 4
