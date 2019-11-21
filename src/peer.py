#! /usr/bin/env python

import time

class Peer:
    def __init__(self, ip, port, num_pieces, piece_len, sock=None, id=None):
        self.id = id
        self.ip = ip
        self.port = port
        self.pieces = bytearray(num_pieces)
        self.num_pieces = num_pieces
        self.last_received = -1
        self.sock = sock
        self.last_processed = 0
        self.already_processed = False
        self.unchoked = False
        self.state = -1
        '''
            -1  -   N/A
             0  -   Sent bitfield/have
             1  -   Sent choke/unchoke
             2  -   Sent interested/not interested
             3  -   Sent request
             4  -   Sent piece

        '''

    def set_id(self, id):
        self.id = id

    def set_sock(self, sock):
        self.sock = sock

    def set_pieces(self, bitfield, size):
        for i in range(len(bitfield)):
            self.pieces[i] = bitfield[i]

    def has_piece(self, piece):
        if piece < 0 or piece >= self.num_pieces:
            return False
        elt = int(piece / 8)
        off = int(piece % 8)
        return 1 == ((self.pieces[elt] & (1 << (7-off))) >> (7-off))

    def set_piece(self, piece, val):
        if piece < 0 or piece >= self.num_pieces:
            return False
        elt = int(piece / 8)
        off = int(piece % 8)
        if val:
            self.pieces[elt] = self.pieces[elt] | (1 << (7-off))
        else:
            self.pieces[elt] = self.pieces[elt] & (~(1 << (7-off)))
        return True


    def process(self, torrent, unchoked_peers, seed, in_progress, data):
        self.already_processed = True
        self.last_processed = int(time.time())
        try:
            m = self.state
            if m == 0:
                return 1
            elif m == 2:
                return 2
            elif self.unchoked:
                return 3
            elif not self.unchoked:
                if m == 1:
                    return 4
            else:
                return -1
        except:
            print('Failed to process a peer.')
            pass
