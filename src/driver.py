#! /usr/bin/env python

import hashlib
import bencode
import random
import torrentfile
import tracker
import socket
import sys
import time
import peer
import getopt
import select
import handler
from struct import *

def usage():
    print('-f <torrentfilename> [--seed]')
    sys.exit(2)

# Take torrent file name as -f arg
filename = None
seed = False

try:
    opts, args = getopt.getopt(sys.argv[1:], 'sf:', ['seed','file='])
except getopt.GetoptError:
    usage()

for opt, arg in opts:
    if opt in ('-f', '--file'):
        filename = arg
    elif opt in ('-s', '--seed'):
        seed = True
    else:
        usage()

if filename is None:
    usage()

# Port for incoming connections
listen_port = 6889

print("Connecting to tracker...")

# Read in file and send tracker request
peer_id = "-PR01"
id_int = int(random.random()*pow(10,15))
peer_id += str(id_int)
peer_id = peer_id + ("x" * (20 - len(peer_id)))
torrent = torrentfile.parse_torrent_file(filename)
print("Sending tracker request...")
#resp = tracker.tracker_request(torrent, peer_id, listen_port, False)

# Keep track of peers and who has been unchoked/has unchoked me
#if resp is None:
#    print('Tracker Failure.')
#    sys.exit(-1)

peers = []#tracker.get_peers(resp["peers"], torrent.num_pieces, torrent.total_len)
addr_to_peer = {}
ids_to_peers = {}
sock_to_peer = {}
active_peers = []
unchoked_me = []
unchoked_peers = []
sent_interested = []


# Pieces being downloaded, randomly choose up to 5 pieces
in_progress = []
num_prog = min(5, torrent.num_pieces)
for i in range(num_prog):
    r = random.randint(0,torrent.num_pieces-1)
    while r in in_progress:
        r = random.randint(0,torrent.num_pieces-1)
    in_progress.append(r)

# Actual data received from peers
data = {}
for f in in_progress:
    data[f] = ''

# This is for testing purposes, I'll have to figure out how to properly get this started again sometime
p = peer.Peer('192.168.2.3', 6889, torrent.num_pieces, torrent.piece_len)
peers.append(p)
# Map ips to peers
for peer in peers:
    addr_to_peer[peer.ip] = peer


# Get info_hash
hash = hashlib.sha1()
bencoded_info = bencode.bencode(torrent.info)
hash.update(bencoded_info)
info_hash = hash.digest()


# Start listening for incoming connections
listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
own_ip = socket.gethostbyname(socket.gethostname())
t = True
while t:
    try:
        listen_sock.bind((own_ip, listen_port))
        t = False
    except:
        listen_port += 1
listen_sock.listen(1)
listen_sock.setblocking(0)
listen_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

if seed:
    if not torrent.load_file():
        print('Seeding requires the complete file.')
        exit(2)


# Setup for select
sock_list = [listen_sock]

print("Handshaking peers (this will take a few seconds)...")

# Send and receive handshakes with all peers
handshook = []
for peer in peers:
    if (handler.handshake_out(peer, info_hash, peer_id, ids_to_peers, addr_to_peer, sock_to_peer, sock_list)):
            active_peers.append(peer)
            handler.send_interested(peer.sock, peer)
            handler.send_bitfield(peer.sock, peer, torrent.complete)

    handshook.append(peer)
    sys.stdout.write("\rConnected to %s peers..." % str(len(active_peers)))
    sys.stdout.flush()

last_piece = int(time.time())
start_time = last_piece
seeding = 0
complete = 0

# Begin select loop
while True:
    if int(time.time()) > start_time and not seed:
        sys.stdout.write("\rDownload started... " + str(torrent.percent_complete()) + '% @ ' + str(int(torrent.downloaded/(int(time.time())-start_time))) + ' bytes/sec')
        sys.stdout.flush()
    elif seed:
        sys.stdout.write('{:<20}'.format("\rSeeding." + '.'*(seeding/1000)))
        sys.stdout.flush()
        seeding = (seeding+1)%10000

    readable, writable, exceptional = select.select(sock_list,[],sock_list,1)

    for sock in readable:
        if sock is listen_sock:
            # New connection
            connection, client_address = sock.accept()
            connection.setblocking(0)
            sock_list.append(connection)
        else:
            # Connection with peer
            type, message = handler.parse_message(sock)
            if sock in sock_to_peer:
                sock_to_peer[sock].last_processed = int(time.time())
                sock_to_peer[sock].already_processed = False
            if type == -2:
    	           # Handle incoming handshake
                #print("Received handshake.")
                if (handler.handshake_in(sock, message, torrent, peer_id, info_hash, addr_to_peer, sock_to_peer, peers, active_peers, ids_to_peers, torrent.total_len, handshook)):
                    if sock in sock_to_peer:
                        peer = sock_to_peer[sock]
                        handler.send_bitfield(sock, peer, torrent.complete)
            elif type == -1:
                # Handle keep-alive
                #print('Keep Alive')
                handler.send_keepalive(sock)
            elif type == 0:
    	        # Handle choke
                #print('Choke')
                if sock in sock_to_peer:
                    peer = sock_to_peer[sock]
                    handler.handle_choke(sock, peer, unchoked_me, unchoked_peers)
            elif type == 1:
                # Handle unchoke
                #print('Unchoke')
                if sock in sock_to_peer:
                    peer = sock_to_peer[sock]
                    if handler.handle_unchoke(sock, peer, unchoked_me, unchoked_peers, seed):
                        if peer in unchoked_me and peer in unchoked_peers and not seed:
                            handler.send_request(sock, peer, torrent, in_progress, data)
            elif type == 2:
                # Handle interested
                #print('Interested')
                if sock in sock_to_peer:
                    peer = sock_to_peer[sock]
                    handler.handle_interested(sock, peer, active_peers, unchoked_peers, seed)
            elif type == 3:
                # Handle not interested
                #print('Not Interested')
                if sock in sock_to_peer:
                    peer = sock_to_peer[sock]
                    handler.handle_not_interested(peer, active_peers, unchoked_peers, unchoked_me)
            elif type == 4:
    	        # Handle have
                #print('Have')
                if sock in sock_to_peer:
                    peer = sock_to_peer[sock]
                    if peer in active_peers:
                        handler.parse_have(peer, message)
                        if not peer in sent_interested:
                            handler.send_interested(sock, peer)
    	                    #handler.send_bitfield(sock, torrent.complete)
                            sent_interested.append(peer)
            elif type == 5:
    	        # Handle bitfield
                #print('Bitfield')
                if sock in sock_to_peer:
                    peer = sock_to_peer[sock]
                    if peer in active_peers:
                        handler.parse_bitfield(peer, message, torrent.total_len)
    	                #if peer in unchoked_peers or len(unchoked_peers) < 1:
    	                    #handler.send_unchoke(sock, peer, unchoked_peers)
                        if not peer in sent_interested:
                            handler.send_interested(sock, peer)
    	                #    handler.send_bitfield(sock, torrent.complete)
                            sent_interested.append(peer)
                        #if peer in unchoked_peers or (len(unchoked_peers) < 7 or (seed and len(unchoked_peers) < 7)):
                    #        handler.send_unchoke(sock, peer, unchoked_peers, seed)
            elif type == 6:
    	        # Handle request
                #print('Request')
                if sock in sock_to_peer:
                    peer = sock_to_peer[sock]
                    if peer in unchoked_peers:
                        handler.send_piece(sock, peer, message, torrent)
                        if seed:
                            last_piece = int(time.time())
            elif type == 7:
    	        # Handle piece
                #print('Piece')
                if sock in sock_to_peer and not seed:
                    peer = sock_to_peer[sock]
                    last_piece = int(time.time())
                    handler.handle_piece(sock, message, data, in_progress, torrent, sock_to_peer, seed)
                    if not seed:
                        if torrent.pieces_left <= 0:
                            seed = True
                            print
                        else:
                            handler.send_request(sock, peer, torrent, in_progress, data)
            else:
                pass
        for sock in exceptional:
            if sock in sock_to_peer:
                peer = sock_to_peer[sock]
                if peer in active_peers:
                    active_peers.remove(peer)
                if peer.id in ids_to_peers:
                    ids_to_peers.pop(peer.id)
                if peer in unchoked_me:
                    unchoked_me.remove(peer)
                if peer in unchoked_peers:
                    unchoked_peers.remove(peer)
                if peer in handshook:
                    handshook.remove(peer)
            print('Peer hungup: ' + str(peer.ip))
            sock_list.remove(sock)
            sock.close()

    tx = int(time.time())
    '''for peer in active_peers:
        if not peer.sock in readable and (tx - peer.last_processed) > 4:
            peer.last_processed = tx
            if peer.already_processed:
                # Peer has already gone through this process, choke it
                handler.send_choke(peer.sock, peer, unchoked_peers)
                # Randomly select new peer to unchoke (that isn't this one)
                while len(unchoked_peers) < 7:
                    attempts = 5
                    r = random.randint(0, len(active_peers))
                    print str(r) + ' of ' + str(len(active_peers))
                    while ((not active_peers[r] in unchoked_me) or active_peers[r] == peer) and (attempts > 0):
                        r = random.randint(0, len(active_peers))
                    new_peer = active_peers[r]
                    new_peer.last_processed = tx
                    new_peer.already_processed = False
                    # Send new peer unchoke
                    handler.send_unchoke(new_peer.sock, new_peer, unchoked_peers, seed)
            else:
                # Process peer (Usually just resending a message that got no response)
                t = peer.process(torrent, unchoked_peers, seed, in_progress, data)
                if not t == -1:
                    handler.process(peer, t, torrent, unchoked_peers, seed, in_progress, data)
            break'''
