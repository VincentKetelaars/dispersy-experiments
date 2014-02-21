'''
Created on Nov 27, 2013

@author: Vincent Ketelaars
'''

import argparse
from src.definitions import MAX_MTU, SQLITE_DATABASE, TOTAL_RUN_TIME,\
    BLOOM_FILTER_UPDATE, ENABLE_CANDIDATE_WALKER, SWIFT_BINPATH

def main():    
    parser = argparse.ArgumentParser(description='Start Dispersy instance')
    parser.add_argument("-b", "--bloomfilter", type=float, default=BLOOM_FILTER_UPDATE, help="Send bloom filter every # seconds")
    parser.add_argument("-d", "--directories", nargs="+", default=[], help="List directories of files to monitor")
    parser.add_argument("-D", "--destination", help="List directory to put downloads")
    parser.add_argument("-f", "--files", nargs="+", default=[], help="List files to send")
    parser.add_argument("-F", "--file_timestamp_min", type=float, help="Minimum file modification time")
    parser.add_argument("-g", "--gateways", nargs="+", default=[], help="Provide gateways for interfaces, space separated: wlan0=192.168.0.1")
    parser.add_argument("-l", "--listen", nargs="+", default=[], help="List of sockets to listen to [port, ip4[:port], ip6[:port]], space separated")
    parser.add_argument("-m", "--mtu", type=int, default=MAX_MTU, help="Maximum number of bytes per datagram")
    parser.add_argument("-p", "--peers", nargs="+", default=[], help="List of Dispersy peers [port, ip4[:port], ip6[:port]], space separated")
    parser.add_argument("-q", "--sqlite_database", default=SQLITE_DATABASE, help="SQLite Database directory")
    parser.add_argument("-s", "--swift", default=SWIFT_BINPATH, help="Swift binary path, defaults to libswift/swift")
    parser.add_argument("-t", "--time", type=float, default=TOTAL_RUN_TIME, help="Set runtime")
    parser.add_argument("-w", "--work_dir", default=".", help="Working directory")
    parser.add_argument("-W", "--walker", action='store_true', default=ENABLE_CANDIDATE_WALKER, help="Enable candidate walker")
    args = parser.parse_args()
        
    return (args.destination, args.swift), {"dispersy_work_dir":args.work_dir, "sqlite_database":args.sqlite_database,
            "swift_work_dir":args.work_dir, "listen":args.listen, "peers":args.peers, "file_directories":args.directories,
            "files":args.files, "file_timestamp_min":args.file_timestamp_min, "run_time":args.time, 
            "bloomfilter_update":args.bloomfilter, "walker":args.walker, "gateways":args.gateways, "mtu":args.mtu}