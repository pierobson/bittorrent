#! /usr/bin/env python

import hashlib
import random
import urllib
import urllib2
import torrentfile
import bencode
import socket
from peer import Peer
from struct import *

def tracker_request(meta, peer_id, port, shutdown):
    hash = hashlib.sha1()
    bencoded_info = bencode.bencode(meta.info)
    hash.update(bencoded_info)
    info_hash = hash.digest()

    args = {}
    args["info_hash"] = info_hash
    info_hash = urllib.urlencode(args)

    args = {}
    args["peer_id"] = str(peer_id)
    peer_id = urllib.urlencode(args)

    args = {}
    args["port"] = port
    port = urllib.urlencode(args)

    args = {}
    uploaded = meta.uploaded
    args["uploaded"] = str(uploaded)
    uploaded = urllib.urlencode(args)

    args = {}
    downloaded = meta.downloaded
    args["downloaded"] = str(downloaded)
    downloaded_en = urllib.urlencode(args)


    args = {}
    left = meta.total_len - downloaded
    args["left"] = str(left)
    left = urllib.urlencode(args)

    args = {}
    # Accept compact responses yet
    args["compact"] = str(1)
    compact = urllib.urlencode(args)

    args = {}
    event = ""
    if (downloaded == 0):
        event = "started"
    elif (shutdown):
        event = "stopped"
    elif(left == 0):
        event = "completed"
    if (not (len(event) == 0)):
        args["event"] = event
        event = urllib.urlencode(args)

    url_args = info_hash + "&" + peer_id + "&" + port + "&" + uploaded + "&" + downloaded_en + "&" + left + "&" + compact
    if (not (len(event) == 0)):
        url_args = url_args + "&" + event

    if (meta.backup_announces is None or len(meta.backup_announces)==0):
        url = meta.announce + "?" + url_args
        #print(url)
        contents = urllib2.urlopen(url).read()
        return bencode.bdecode(contents.rstrip())
    else:
        # Query announce servers in order until one gives a response
        i = 0
        contents = ""
        while i < len(meta.backup_announces):
            announce = meta.backup_announces[i][0]
            url = announce + "?" + url_args
            contents = urllib2.urlopen(url).read()
            c = bencode.bdecode(contents)
            if (not 'failure reason' in c):
                return c
            i +=1
        return None

def get_peers(peer_val, elts, length):
    peers = []
    if (isinstance(peer_val, basestring)):
        # Compact response (binary)
        i = 0
        while (i < len(peer_val)):
            curr_peer = peer_val[i:i+6]
            ip_addr = socket.inet_ntoa(curr_peer[0:4])
            port = int(unpack("!H", curr_peer[4:6])[0])
            peers.append(Peer(ip_addr, port, elts, length))
            i+=6
        return peers
    else:
        # Dictionary repsonse???
        for peer in peer_val:
            peers.append(Peer(peer['ip'], peer['port'], elts, length))
        return peers
