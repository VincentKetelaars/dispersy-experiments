'''
Created on Sep 10, 2013

@author: Vincent Ketelaars
'''
import os
import socket
from datetime import datetime

"""
API
"""

MESSAGE_KEY_STOP = 0
MESSAGE_KEY_STATE = 1
MESSAGE_KEY_ADD_FILE = 2
MESSAGE_KEY_ADD_MESSAGE = 3
MESSAGE_KEY_ADD_PEER = 4
MESSAGE_KEY_ADD_SOCKET = 5
MESSAGE_KEY_INTERFACE_UP = 6
MESSAGE_KEY_MONITOR_DIRECTORY = 7
MESSAGE_KEY_RECEIVE_FILE = 8
MESSAGE_KEY_API_MESSAGE = 9
MESSAGE_KEY_SWIFT_STATE = 10
MESSAGE_KEY_SOCKET_STATE = 11
MESSAGE_KEY_SWIFT_PID = 12
MESSAGE_KEY_SWIFT_INFO = 13
MESSAGE_KEY_DISPERSY_INFO = 14
MESSAGE_KEY_BAD_SWARM = 15

"""
STATE
"""
# States
STATE_NOT = -1
STATE_INITIALIZED = 0
STATE_RUNNING = 1
STATE_STOPPED = 2
STATE_DONE = 3
STATE_RESETTING = 4

"""
DISPERSY
"""

SECURITY = u"medium"

# generated: Wed Aug  7 14:21:33 2013
# curve: medium <<< NID_sect409k1 >>>
# len: 409 bits ~ 104 bytes signature
# pub: 128 307e301006072a8648ce3d020106052b81040024036a0004004b2c2fbbf036a0ae1dedf4420ff724869e324bc63064ec2e7bad062a7a9c7f31a7c3ff17a11fd582c9eb8b727dacb228afceb2002ad6e916efd4531e79f040341c7259c99938aae9f6ece17c5075b7ab8e9c92f7ff4493468d1e354a31d139e73928266b824fe3
# prv: 178 3081af0201010433252d8205db8f95bbe82a6668ba04c9e13db70b7c3669b451f5d18c24590b8ccb6033f37a9c49b956c84e412a0992f6f76f25ffa00706052b81040024a16c036a0004004b2c2fbbf036a0ae1dedf4420ff724869e324bc63064ec2e7bad062a7a9c7f31a7c3ff17a11fd582c9eb8b727dacb228afceb2002ad6e916efd4531e79f040341c7259c99938aae9f6ece17c5075b7ab8e9c92f7ff4493468d1e354a31d139e73928266b824fe3
# pub-sha1 04b6c5a1eafb928ca5763a8bb93c5ad5a44c971e
# prv-sha1 31510601257b8649d8280cf3334e52de646d4aa9
# -----BEGIN PUBLIC KEY-----
# MH4wEAYHKoZIzj0CAQYFK4EEACQDagAEAEssL7vwNqCuHe30Qg/3JIaeMkvGMGTs
# LnutBip6nH8xp8P/F6Ef1YLJ64tyfayyKK/OsgAq1ukW79RTHnnwQDQcclnJmTiq
# 6fbs4XxQdberjpyS9/9Ek0aNHjVKMdE55zkoJmuCT+M=
# -----END PUBLIC KEY-----
# -----BEGIN EC PRIVATE KEY-----
# MIGvAgEBBDMlLYIF24+Vu+gqZmi6BMnhPbcLfDZptFH10YwkWQuMy2Az83qcSblW
# yE5BKgmS9vdvJf+gBwYFK4EEACShbANqAAQASywvu/A2oK4d7fRCD/ckhp4yS8Yw
# ZOwue60GKnqcfzGnw/8XoR/Vgsnri3J9rLIor86yACrW6Rbv1FMeefBANBxyWcmZ
# OKrp9uzhfFB1t6uOnJL3/0STRo0eNUox0TnnOSgma4JP4w==
# -----END EC PRIVATE KEY-----

MASTER_MEMBER_PUBLIC_KEY = "307e301006072a8648ce3d020106052b81040024036a0004004b2c2fbbf036a0ae1dedf4420ff724869e324bc63064ec2e7bad062a7a9c7f31a7c3ff17a11fd582c9eb8b727dacb228afceb2002ad6e916efd4531e79f040341c7259c99938aae9f6ece17c5075b7ab8e9c92f7ff4493468d1e354a31d139e73928266b824fe3".decode("HEX")

RANDOM_PORTS = (socket.IPPORT_USERRESERVED, 2**16 - 1)

DEFAULT_MESSAGE_COUNT = 1
DEFAULT_MESSAGE_DELAY = 0.0 # Seconds

# Time in seconds
SLEEP_TIME = 0.5
TOTAL_RUN_TIME = 10
BLOOM_FILTER_UPDATE = 5.0
REPORT_DISPERSY_INFO_TIME = 1.0

DEST_DIR = os.getenv("HOME") + "/Desktop/tests_dest"
SWIFT_BINPATH = os.getenv("HOME") + "/git/dispersy-experiments/libswift/swift" #os.getenv("HOME") + "/svn/libswift/ppsp/swift" # "/git/dispersy-experiments/tribler/Tribler/SwiftEngine/swift"
DISPERSY_WORK_DIR = os.getenv("HOME") + "/Music/"+ datetime.now().strftime("%Y%m%d%H%M%S") + "_" + str(os.getpid()) + "/"
SQLITE_DATABASE = ":memory:"
ENABLE_CANDIDATE_WALKER = False

SEPARATOR = ";;"
PATH_SEPARATOR = "/"

DISTRIBUTION_DIRECTION = u"ASC" # "ASC" or "DESC"
DISTRIBUTION_PRIORITY = 127
NUMBER_OF_PEERS_TO_SYNC = 1
HASH_LENGTH = 40

SMALL_FILE_MESSAGE_NAME = u"small_file_message"
FILE_HASH_MESSAGE_NAME = u"file_hash_message"
ADDRESSES_MESSAGE_NAME = u"addresses_message"
API_MESSAGE_NAME = u"api_message"

MAX_FILE_SIZE = 2**16-60

# Filepusher
FILETYPES_NOT_TO_SEND = [".mhash",".mbinmap"]
FILENAMES_NOT_TO_SEND = ["swifturl-"]

"""
Tests
"""
TIMEOUT_TESTS = 10 # Seconds

"""
Swift
"""

LIBEVENT_LIBRARY = "/usr/local/lib"
MOREINFO = True # Don't change this to False because it might affect things
DELETE_CONTENT = False # If True it will be deleted immediately when finished, after callback
PEXON = False # If True Swift might disseminate data to unauthorized peers

"""
Timeout
"""
TIMEOUT_INTRODUCTION_REQUEST = 5.0 # Seconds

"""
Git Repository
"""
REPOSITORY_HOME = os.getenv("HOME") + "/git/dispersy-experiments"

"""
UAV Repository
"""
UAV_REPOSITORY_HOME = os.getenv("HOME") + "/svn/norut/uav/trunk"