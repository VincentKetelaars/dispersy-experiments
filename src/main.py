'''
Created on Nov 27, 2013

@author: Vincent Ketelaars
'''

import argparse
from dispersy.dispersy import Dispersy
from src.address import Address

def main(call, callback=None):    
    parser = argparse.ArgumentParser(description='Start Dispersy instance')
    parser.add_argument("-b", "--bloomfilter", help="Send bloom filter every # seconds")
    parser.add_argument("-d", "--directory", help="List directory of files to send")
    parser.add_argument("-D", "--destination", help="List directory to put downloads")
    parser.add_argument("-f", "--files", nargs="+", help="List files to send")
    parser.add_argument("-l", "--listen", nargs="+", help="List of sockets to listen to (port, ip4, ip6), space separated")
    parser.add_argument("-p", "--peers", nargs="+", help="List of Dispersy peers(port, ip4, ip6), space separated")
    parser.add_argument("-q", "--sqlite_database", default=u":memory:", help="SQLite Database directory")
    parser.add_argument("-s", "--swift", help="Swift binary path")
    parser.add_argument("-t", "--time", type=float, help="Set runtime")
    parser.add_argument("-w", "--work_dir", help="Working directory")
    parser.add_argument("-W", "--walker", action='store_true', help="Enable candidate walker")
    args = parser.parse_args()
    
    from src.definitions import DEST_DIR, SWIFT_BINPATH, TOTAL_RUN_TIME, DISPERSY_WORK_DIR, SQLITE_DATABASE, \
    BLOOM_FILTER_UPDATE, ENABLE_CANDIDATE_WALKER
    
    if args.time:
        TOTAL_RUN_TIME = args.time
        
    if args.destination:
        DEST_DIR = args.destination
    
    if args.swift:
        SWIFT_BINPATH = args.swift
        
    if args.work_dir:
        DISPERSY_WORK_DIR = args.work_dir
        
    if args.sqlite_database:
        SQLITE_DATABASE = args.sqlite_database
        
    if args.bloomfilter:
        BLOOM_FILTER_UPDATE = args.bloomfilter
        
    if args.walker:
        ENABLE_CANDIDATE_WALKER = args.walker
        
    localip = "127.0.0.1"
    local_interface = Dispersy._guess_lan_address(Dispersy._get_interface_addresses())
    if local_interface is not None:
        localip = local_interface.address
        
    listen = []
    if args.listen:
        for a in args.listen:
            addr = Address.unknown(a)
            if addr.is_wildcard_ip():
                addr.set_ipv4(localip)
            listen.append(addr)
    
    peers = []
    if args.peers:
        for p in args.peers:
            addr = Address.unknown(p)
            if addr.is_wildcard_ip():
                addr.set_ipv4(localip)
            peers.append(addr)
        
    c = call(DEST_DIR, SWIFT_BINPATH, dispersy_work_dir=DISPERSY_WORK_DIR, sqlite_database=SQLITE_DATABASE,
            swift_work_dir=DEST_DIR, listen=listen, peers=peers, files_directory=args.directory,
            files=args.files, run_time=TOTAL_RUN_TIME, bloomfilter_update=BLOOM_FILTER_UPDATE,
            walker=ENABLE_CANDIDATE_WALKER, callback=callback)
    c.start()
    return c