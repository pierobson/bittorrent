#! /usr/bin/env python

from torrent import Torrent
import bencode

def to_torrent(meta):
    info = meta["info"]
    #print meta
    announce = None
    if 'announce' in meta:
        announce = meta["announce"]
    backup_announces = None
    if 'announce-list' in meta:
        backup_announces = meta["announce-list"]
    tor = Torrent(info, announce, backup_announces)
    return tor

def parse_torrent_file(file_path):
    torrent_file = open(file_path, "r")
    encoded_data = torrent_file.read().rstrip()
    meta = bencode.bdecode(encoded_data)
    return to_torrent(meta)
