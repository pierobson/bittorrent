#! /usr/bin/env python

from struct import *
from peer import Peer
import random
import select
import sys
import math
import binascii
import shutil
import hashlib
import time
import socket


def parse_message(sock):
    #print('Parse message')
    length_str = ""
    bytes = 0
    expected = 4

    try:
        while bytes < expected:
            s = sock.recv(expected - bytes)
            bytes += len(s)
            length_str += s
    except:
        print('Failed to get first 4 bytes.')
        return (-5,None)

    length = int(unpack('!L', length_str)[0])
    if length == 0:
        # Keep alive message
        return (-1, None)
    elif length_str == '\x13Bit':
        # Incoming handshake
        try:
            while bytes < 68:
                s = sock.recv(68-bytes)
                bytes += len(s)
                length_str += s
        except:
            return (-5,None)
        return (-2, length_str)
    else:
        bytes = 0
        message = ""
        try:
            while bytes < length:
                s = sock.recv(length - bytes)
                bytes += len(s)
                message += s
        except:
            return (-5,None)

        if bytes < length:
            return (-5, None)

        type = message[0]
        payload = None
        if len(message) > 1:
            payload = message[1:]
        return (int(unpack('!B', type)[0]), payload)


def handshake_out(peer, info_hash, peer_id, ids_to_peers, addr_to_peer, sock_to_peer, sock_list):
    handshake = "\x13BitTorrent protocol\x00\x00\x00\x00\x00\x00\x00\x00"
    handshake += info_hash + peer_id
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(0)
    sock_list.append(sock)
    peer.set_sock(sock)

    # Keep response time short to speed up start (only need ~30 peers to respond)
    sock.settimeout(0.5)
    addr = (peer.ip, peer.port)
    try:
        sock.connect(addr)
        sock.sendall(handshake)
    except:
        #print("Failed to send handshake.")
        return False
    try:
        shake = ""
        pstr = ""
        bytes = 0
        expected = 20

        attempts = 10
        while bytes < expected:
            if attempts < 1:
                #print("Failed to receive pstr.")
                return False
            str = sock.recv(expected - bytes)
            pstr += str
            bytes += len(str)
            attempts -= 1

        if (not "\x13BitTorrent protocol" == pstr):
            #print("Invalid handshake received.")
            return False

        expected = 48
        bytes = 0
        attempts = 15
        while bytes < expected:
            if attempts < 1:
                print("Failed to receive the rest of handshake.")
                return False
            str = sock.recv(expected - bytes)
            shake += str
            bytes += len(str)
            attempts -= 1

        if (not shake[8:28] == info_hash):
            print("Invalid handshake info_hash.")
            return False
        peer.set_id(shake[28:])
        ids_to_peers[peer.id] = peer
        addr_to_peer[peer.ip] = peer
        sock_to_peer[sock] = peer
        return True
    except:
        print("Failed to receive handshake.")
        return False


def handshake_in(sock, msg, torrent, peer_id, info_hash, addr_to_peer, sock_to_peer, peers, active_peers, ids_to_peers, size, handshook):
    #print('Handshake in')
    peer = None
    if (sock.getpeername()[0] in addr_to_peer):
        peer = addr_to_peer[sock.getpeername()[0]]
    else:
        peer = Peer(sock.getpeername()[0], sock.getpeername()[1], torrent.num_pieces, torrent.piece_len, sock)

    if (not "\x13BitTorrent protocol" == msg[0:20]):
        print("Invalid handshake received.")
        return False

    if (not msg[28:48] == info_hash):
        print("Invalid handshake info_hash.")
        return False
    addr_to_peer[peer.ip] = peer
    if (not peer in peers):
        peers.append(peer)
    if (not peer in active_peers):
        active_peers.append(peer)
    peer.set_id(msg[48:])
    ids_to_peers[peer.id] = peer
    sock_to_peer[sock] = peer

    try:
        if not peer in handshook:
            handshake = "\x13BitTorrent protocol\x00\x00\x00\x00\x00\x00\x00\x00"
            handshake += info_hash + peer_id
            sock.sendall(handshake)
            handshook.append(peer)
            # Responded to handshake
        return True
    except:
        return False

def send_interested(sock, peer):
    #print('send interested')
    interested = "\x00\x00\x00\x01\x02"
    peer.state = 2
    try:
        sock.sendall(interested)
    except:
        #print("Failed to send interested.")
        return False
    return True

def send_bitfield(sock, peer, bitfield):
    #print('send bitfield')
    length = len(bitfield)
    peer.state = 0
    try:
        message = pack('!L', (length+1)) + '\x05' + bitfield
        sock.sendall(message)
    except:
        return False
    return True

def parse_bitfield(peer, bitfield, length):
    #print('parse bitfield')
    peer.set_pieces(bytearray(bitfield), length)

def send_have(sock, peer, piece):
    #print('send have')
    peer.state = 0
    msg = '\x00\x00\x00\x05\x04' + pack('!L', piece)
    try:
        sock.sendall(msg)
    except:
        print('Failed to send have.')
        return False
    return True

def parse_have(peer, message):
    #print('parse have')
    idx = int(unpack('!L', message)[0])
    peer.set_piece(idx, True)

def handle_interested(sock, peer, active_peers, unchoked_peers, seed):
    #print('handle interested')
    if peer in active_peers:
        if len(unchoked_peers) < 7 or (seed and len(unchoked_peers) < 7):
            unchoked_peers.append(peer)
            send_unchoke(sock, peer, unchoked_peers, seed)
        '''else:
            send_choke(sock, peer, unchoked_peers)'''

def handle_not_interested(peer, active_peers, unchoked_peers, unchoked_me):
    #print('handle not interested')
    if peer in active_peers:
        active_peers.remove(peer)
    if peer in unchoked_peers:
        unchoked_peers.remove(peer)
    if peer in unchoked_me:
        unchoked_me.remove(peer)

def send_choke(sock, peer, unchoked_peers):
    #print('send choke')
    peer.unchoked = False
    peer.state = 1
    if peer in unchoked_peers:
        unchoked_peers.remove(peer)
    try:
        choke_msg = str(pack('!L', 1))
        choke_msg += '\x00'
        sock.sendall(choke_msg)
    except:
        print("Failed to send choke.")
        pass


def handle_choke(sock, peer, unchoked_me, unchoked_peers):
    #print('handle choke')
    if peer in unchoked_me:
        unchoked_me.remove(peer)
    '''if peer in unchoked_peers:
        send_choke(sock, peer, unchoked_peers)'''


def send_unchoke(sock, peer, unchoked_peers, seed):
    #print('send unchoke')
    peer.unchoked = True
    peer.state = 1
    if not peer in unchoked_peers and (len(unchoked_peers) < 7  or (seed and len(unchoked_peers) < 7)):
        unchoked_peers.append(peer)
    if peer in unchoked_peers:
        try:
            ##print('Unchoked: ' + peer.ip)
            unchoke_msg = str(pack('!L', 1))
            unchoke_msg += '\x01'
            sock.sendall(unchoke_msg)
        except:
            #print("Failed to send unchoke.")
            pass

def handle_unchoke(sock, peer, unchoked_me, unchoked_peers, seed):
    #print('handle unchoke')
    #print(str(unchoked_peers))
    #print(str(unchoked_me))
    if not peer in unchoked_me:
        unchoked_me.append(peer)
    # Reciprocation
    if peer in unchoked_peers:
        # Send request
        return True
    elif len(unchoked_peers) < 7  or (seed and len(unchoked_peers) < 7):
        # Send unchoke, then send request
        send_unchoke(sock, peer, unchoked_peers, seed)
        return True
    else:
        return False


def send_request(sock, peer, torrent, in_progress, data):
    if len(in_progress) <= 0:
        return
    #print('Sending request to: ' + peer.ip)
    piece = random.choice(in_progress)

    # Try a few times to get a piece that the peer has
    attempts = 10
    while (not peer.has_piece(piece) and attempts > 1):
        piece = random.choice(in_progress)
        attempts -= 1
    if (not peer.has_piece(piece)) or torrent.have_complete(piece):
        return


    # Offset from start of piece is length of what we already have
    offset = int(len(data[piece]))
    request_msg = pack('!L', 13) + '\x06'
    request_msg += pack('!L', piece) + pack('!L', offset)
    request_msg += pack('!L', math.pow(2,14))
    peer.state = 3
    try:
        sock.sendall(request_msg)
    except:
        print("Failed to send request.")
        pass


def send_piece(sock, peer, message, torrent):
    #print('send piece')
    piece = int(unpack('!L', message[0:4])[0])
    byte = int(unpack('!L', message[4:8])[0])
    length = int(unpack('!L', message[8:])[0])

    dat = ''
    if not torrent.have_complete(piece):
        print("Don't have piece.")
        return
    if not length == math.pow(2,14):
        print('REEEEEEEE')
        return
    files = torrent.piece_to_files(piece)


    dat = ''
    piece_len_to_send = int(min(torrent.length_of_piece(piece) - byte, length))
    for i in range(len(files)):
        file = files[i]
        s,e = torrent.eugene(file, piece)
        #print('Piece: ' + str(piece) + ' Offset: ' + str(byte) + ' Length: ' + str(piece_len_to_send))
        fname = torrent.get_filename(file)
        with open(fname, 'r') as asd:
            if e > 0:
                try:
                    asd.read(s + byte)
                    temp = asd.read(piece_len_to_send)
                    #print(str(len(temp)))
                    dat += temp
                    #print('Adding to dat')
                except:
                    #print('Failed to read file.')
                    return
    try:
        piece_msg = pack('!L', (9+piece_len_to_send)) + '\x07' + message[0:4] + message[4:8] + dat
        sock.sendall(piece_msg)
    except:
        print('Failed to send piece.')

def send_keepalive(sock):
    msg = '\x00\x00\x00\x00'
    try:
        sock.sendall(msg)
    except:
        pass


def handle_piece(sock, message, data, in_progress, torrent, socks_to_peers, seed):
    #print('handle piece')
    index = int(unpack('!L', message[0:4])[0])
    begin = int(unpack('!L', message[4:8])[0])
    payload = message[8:]
    # Check this piece should be downloaded
    if (not torrent.have_complete(index)) and index in in_progress and index in data.keys():
        # Check this has next bytes we need
        if begin >= 0 and begin <= len(data[index]):
            # Write to end of piece at most
            start = len(data[index]) - begin
            need = torrent.piece_len - len(data[index])
            end = min(need, len(payload))
            data[index] += payload[start:end]
            torrent.downloaded += (end-start)
            if len(data[index]) == torrent.length_of_piece(index):
                # Piece is complete, check the hash
                hash = hashlib.sha1()
                hash.update(data[index])
                dig = hash.digest()
                #print str(dig)
                #print str(torrent.info['pieces'][index*20:index*20+20])
                if dig == torrent.info['pieces'][index*20:index*20+20]:
                    # Correct hash
                    torrent.set_complete(index)
                    write_to_file(torrent, data, index)

                    del data[index]
                    in_progress.remove(index)

                    # Tell peers you have this piece now
                    for s in socks_to_peers:
                        if not s == sock:
                            send_have(s, peer, index)

                    # If have everything, start seeding
                    if torrent.all_complete():
                        seed = True
                    elif torrent.pieces_left > len(in_progress):
                        # Otherwise, randomly select next piece to download
                        r = random.randint(0, torrent.num_pieces-1)
                        while torrent.have_complete(r) or r in in_progress:
                            r = random.randint(0, torrent.num_pieces-1)
                        in_progress.append(r)
                        data[r] = ''
                else:
                    # Incorrect hash, reset piece
                    print('Piece hash did not match.')
                    data[index] = ''
    return True

# Check torrent.complete to determine where to write in file
def write_to_file(torrent, data, index):
    # Determine which files this piece belongs in
    files = torrent.piece_to_files(index)
    for file in files:
        #   Determine where this piece belongs in the file, relative to the
        #   piece that are already complete
        #
        #   To write properly, need to read/write the file up to the point that
        #   this piece belongs, write this piece, then read/write the rest.
        #
        #   Taking into account very large files, need to write to temporary file,
        #   then rename the file to overwrite what is currently there.
        fname = torrent.get_filename(file)
        # s -> Starting byte in the piece that belongs in this file
        # e -> Ending byte in piece that belongs in this file
        s,e = torrent.borders(fname, index)

        # If the file doesn't exist, create it
        try:
            t = open(fname, 'r')
            t.close()
        except:
            t = open(fname, 'w+')
            t.close()

        with open(fname, 'r') as orig:
            temp_name = fname + '-temp' + str(random.randint(0,12345))
            with open(temp_name, 'a+') as temp:
                # Determine which pieces could be in file,
                offset = 0
                ps, pe = torrent.piece_range(file)
                # First piece in file might not be full piece so do it separately
                sp,ep = torrent.borders(file, ps)
                offset += (ep-sp)
                for pi in range(ps+1,index):
                    # Inc. offset for full pieces written to disk
                    if torrent.have_complete(pi):
                        offset += torrent.piece_len
                # Offset is now # bytes to rewrite to temp
                temp.write(orig.read(offset))
                # Now append new data to temp
                temp.write(data[index][s:e])
                # Now rewrite rest of file
                temp.write(orig.read())
        # Temp is original with new data added in, rename it to overwrite orig
        shutil.move(temp_name, fname)

def process(peer, t, torrent, unchoked_peers, seed, in_progress, data):
    try:
        if t == 1:
            send_bitfield(peer.sock, peer, torrent.complete)
        elif t == 2:
            send_interested(peer.sock, peer)
        elif t == 3:
            send_request(peer.sock, peer, torrent, in_progress, data)
        elif t == 4:
            handler.send_choke(peer.sock, peer, unchoked_peers)
        elif t == -1:
            handler.send_keepalive(peer.sock)
    except:
        print('Failed to process a peer.')
        pass
