#! /usr/bin/env/ python

import math
import hashlib

class Torrent:
    def __init__(self, info=None, announce=None, backup_announces=None):
        self.downloaded = 0
        self.uploaded = 0
        self.num_pieces = 0
        self.announce = announce
        self.backup_announces = backup_announces
        self.info = info
        self.block_len = math.pow(2,14)
        self.blocks_in_piece = 0
        self.files = []
        self.file_ranges = {}
        self.directory = './'
        self.mode = False
        self.total_len = 0
        if 'files' in self.info:
            self.mode = True
        if (not self.info is None):
            self.piece_len = int(self.info['piece length'])
            if (not self.mode):
                self.total_len = int(self.info['length'])
                self.file_ranges[self.directory + self.info['name']] = (0,self.total_len)
                self.files.append(self.info['name'])
            else:
                cul_len = 0
                self.directory += self.info['name'] + '/'
                for file in self.info['files']:
                    self.total_len += int(file['length'])
                    self.files.append(file)
                    self.file_ranges[self.get_filename(file)] = (cul_len, cul_len+int(file['length']))
                    cul_len += int(file['length'])

        if not self.piece_len % self.block_len == 0:
            self.blocks_in_piece = int(self.piece_len / self.block_len)+1
        else:
            self.blocks_in_piece = int(self.piece_len / self.block_len)
        if not self.total_len % self.piece_len == 0:
            self.num_pieces = int(self.total_len/self.piece_len)+1
        else:
            self.num_pieces = int(self.total_len/self.piece_len)
        self.total_blocks = self.num_pieces * self.blocks_in_piece
        t = int(self.num_pieces * self.blocks_in_piece)
        self.elts = 0
        if t % 8 == 0:
            self.elts = t
        else:
            self.elts = t+1
        self.have = bytearray(self.elts)
        x = self.num_pieces % 8
        cl = 0
        if x == 0:
            cl = self.num_pieces/8
        else:
            cl = self.num_pieces/8+1
        self.complete = bytearray(cl)
        self.pieces_left = self.num_pieces



    def set(self, info, announce, backup_announces):
        self.downloaded = 0
        self.uploaded = 0
        self.num_pieces = 0
        self.announce = announce
        self.backup_announces = backup_announces
        self.info = info
        self.block_len = math.pow(2,14)
        self.blocks_in_piece = 0
        self.files = []
        self.file_ranges = {}
        self.mode = False
        self.total_len = 0
        if 'files' in self.info:
            self.mode = True
        if (not self.info is None):
            self.piece_len = int(self.info['piece length'])
            if (not self.mode):
                self.total_len = int(self.info['length'])
                self.file_ranges[self.info['name']] = (0,self.total_len)
                self.files.append(self.info['name'])
            else:
                cul_len = 0
                for file in self.info['files']:
                    self.total_len += int(file['length'])
                    self.files.append(file)
                    self.file_ranges[self.get_filename(file)] = (cul_len, cul_len+int(file['length']))
                    cul_len += int(file['length'])

        if not self.piece_len % self.block_len == 0:
            self.blocks_in_piece = int(self.piece_len / self.block_len)+1
        else:
            self.blocks_in_piece = int(self.piece_len / self.block_len)
        if not self.total_len % self.piece_len == 0:
            self.num_pieces = int(self.total_len/self.piece_len)+1
        else:
            self.num_pieces = int(self.total_len/self.piece_len)
        self.total_blocks = self.num_pieces * self.blocks_in_piece
        t = int(self.num_pieces * self.blocks_in_piece)
        self.elts = 0
        if t % 8 == 0:
            self.elts = t
        else:
            self.elts = t+1
        self.have = bytearray(self.elts)
        x = self.num_pieces % 8
        cl = 0
        if x == 0:
            cl = self.num_pieces/8
        else:
            cl = self.num_pieces/8+1
        self.complete = bytearray(cl)
        self.pieces_left = self.num_pieces


    def has_block(self, elt, idx):
        if elt < 0 or elt >= len(self.have):
            return False
        if idx < 0 or idx > 7:
            return False
        return 1 == self.have[elt] & ((1 << (7-idx)) >> (7-idx))


    def set_block(self, elt, idx, val):
        if elt < 0 or elt >= len(self.have):
            return False
        if idx < 0 or idx > 7:
            return False
        if val:
            self.have[elt] = self.have[elt] | (1 << (7-idx))
        else:
            self.have[elt] = self.have[elt] & (~(1 << (7-idx)))
        return True

    def set_complete(self, piece):
        elt = int(piece / 8)
        idx = int(piece % 8)
        self.complete[elt] = self.complete[elt] | (1 << (7-idx))
        self.pieces_left -= 1


    def have_piece(self, piece):
        piece_start = piece * self.blocks_in_piece
        for i in range(self.blocks_in_piece):
            if not self.has_block(self, self.get_block_idx(piece, i)):
                return False
        self.set_complete(piece)
        return True


    def have_complete(self, piece):
        if piece < 0 or piece >= self.num_pieces:
            return False
        elt = int(piece / 8)
        idx = int(piece % 8)
        return 1 == int((self.complete[elt] & (1 << (7-idx))) >> (7-idx))

    def all_complete(self):
        for p in range(self.num_pieces):
            if not self.have_complete(p):
                return False
        return True

    def get_block_idx(self, piece, block):
        if (piece < 0 or piece >= self.num_pieces):
            return (-1,-1)
        if (block < 0 or block >= self.blocks_in_piece):
            return (-1,-1)
        pos = (piece * self.blocks_in_piece) + block
        elt = block / 8
        idx = block % 8
        return (elt, idx)

    def borders(self, file, piece):
        x = -1
        y = -1
        if self.file_in_piece(file, piece):
            start, end = self.file_ranges[file]
            pstart = piece * self.piece_len
            pend = pstart + self.piece_len
            if start < pstart:
                x = 0
            else:
                x = start-pstart
            if end > pend:
                y = self.piece_len
            else:
                y = self.piece_len - (pend-end)
        return (x,y)

    # Return byte offset in file of piece start. Basically reverse of borders()
    def eugene(self, file, piece):
        x = -1
        y = -1
        filename = self.get_filename(file)
        if self.file_in_piece(filename, piece):
            start, end = self.file_ranges[filename]
            pstart = piece * self.piece_len
            pend = pstart + self.piece_len
            if pstart < start:
                x = 0
            else:
                x = pstart-start
            if pend > end:
                y = end - max(pstart, start)
            else:
                y = pend - max(pstart, start)
        return (x,y)

    def length_of_piece(self, piece):
        if piece == self.num_pieces-1:
            # Last piece might be shorter
            start = piece*self.piece_len
            return self.total_len - start
        elif piece in range(self.num_pieces):
            # Full piece
            return self.piece_len
        else:
            # DNE
            return -1

    def piece_to_files(self, piece):
        fs = []
        if (not self.mode) and piece < self.num_pieces:
            # Single file
            fs.append(self.files[0])
        else:
            for file in self.files:
                if self.file_in_piece(file, piece):
                    fs.append(file)
        return fs

    def piece_range(self, file):
        if file in self.file_ranges:
            s,e = self.file_ranges[file]
            # First piece in the file
            fp = s / self.piece_len
            # Last piece in the file, check if ends on piece border
            lp, lpo = divmod(e, self.piece_len)
            if lpo == 0:
                lp -= 1
            return (fp,lp)
        return (-1,-1)

    def file_in_piece(self, file, piece):
        if (not self.mode) and piece < self.num_pieces and piece >= 0:
            return True
        if file in self.file_ranges:
            start, end = self.file_ranges[file]
            pstart = piece * self.piece_len
            pend = pstart + self.piece_len
            if start in range(pstart, pend) or end in range(pstart, pend):
                return True
        return False

    def get_filename(self, file):
        if not self.mode:
            return self.directory + self.files[0]
        else:
            filename = self.directory
            for i in range(len(file['path'])):
                filename += file['path'][i]
                if i < len(file['path']) - 1:
                    filename += '/'
            return filename

    def file_len(self, filename):
        if not self.mode:
            return self.total_len
        else:
            return self.file_ranges[filename][1] - self.file_ranges[filename][0]

    def percent_complete(self):
        return int(self.downloaded/self.total_len)*100


    # Reads the file to make sure it matches the hash, sets complete accordingly
    def load_file(self):
        hashed = ''
        piece = ''
        bytes_piece = self.piece_len
        for i in range(len(self.files)):
            with open(self.get_filename(self.files[i]), 'r') as file:
                bytes_read = 0
                filename = self.get_filename(self.files[i])
                file_len = self.file_len(filename)
                print('Verifying file: ' + filename)
                while bytes_read < file_len:
                    bytes_to_read = min(bytes_piece, file_len-bytes_read)
                    piece += file.read(bytes_to_read)
                    bytes_read += bytes_to_read
                    bytes_piece -= bytes_to_read
                    if bytes_piece == 0 or len(self.files) <= (i+1):
                        hash = hashlib.sha1()
                        hash.update(piece)
                        hashed += hash.digest()
                        piece = ''
                        bytes_piece = self.piece_len
        if hashed == self.info['pieces']:
            for piece in range(self.num_pieces):
                self.set_complete(piece)
        return hashed == self.info['pieces']
