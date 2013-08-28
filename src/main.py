'''
Created on Aug 7, 2013

@author: Vincent Ketelaars

This is the main file which starts up an instance of Dispersy.
'''

import random
import time
import os
import argparse
from os.path import expanduser
from datetime import datetime
from thread import get_ident

from dispersy.callback import Callback
from dispersy.endpoint import StandaloneEndpoint
from dispersy.dispersy import Dispersy
from dispersy.candidate import WalkCandidate

from src.extend.community import MyCommunity
from src.extend.endpoint import MultiEndpoint

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

import logging.config

def create_mycommunity(dispersy):    
    master_member = dispersy.get_member(MASTER_MEMBER_PUBLIC_KEY)
    my_member = dispersy.get_new_member(SECURITY)
    return MyCommunity.join_community(dispersy, master_member, my_member)
        
def single_callback_single_dispersy():
    # Create Dispersy object
    callback = Callback("MyDispersy")
    port1 = random.randint(10000, 20000)
    #port2 = random.randint(10000, 20000)
    endpoint = MultiEndpoint()
    endpoint.add_endpoint(StandaloneEndpoint(port1))
    #endpoint.add_endpoint(StandaloneEndpoint(port2))
    endpoint = StandaloneEndpoint(port1);
    
    working_dir = u"."
    dt = datetime.now()
    sqlite_database = expanduser("~") + u"/Music/"+ dt.strftime("%Y%m%d%H%M%S") + "_" + unicode(port1)
    #sqlite_database = u":memory:"
    dispersy = Dispersy(callback, endpoint, working_dir, sqlite_database) # Multiple instances, same database gives errors?
    
    dispersy.start()
    print "Dispersy is listening on port %d" % dispersy.lan_address[1]
    
    community = callback.call(create_mycommunity, (dispersy,))
    callback.register(community.create_my_messages, (1,), delay=5.0)
    
    return (community, dispersy)
        
def main(num_instances, show_logs):
    if show_logs:
        logger_conf = os.path.abspath(os.environ.get("LOGGER_CONF", "logger.conf"))
        print "Logger using configuration file: " + logger_conf
        logging.config.fileConfig(logger_conf)
        logger = logging.getLogger(__name__)
    
    dispersy_list = []
    community = None
    for i in range(num_instances):
        community, dispersy = single_callback_single_dispersy()
        dispersy_list.append(dispersy)
    
    for dispersy in dispersy_list:
        for other in dispersy_list:
            if dispersy != other:
                dispersy.create_introduction_request(community,
                                                     WalkCandidate(other.lan_address, False, other.lan_address, other.wan_address, u"unknown"), 
                                                     True, 
                                                     True)
        
    try:
        time.sleep(25)
    except:
        print "Did you do something?" + str(dispersy.endpoint.get_address()[1])
    finally:
        for dispersy in dispersy_list:
            dispersy.stop()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Start Dispersy instance(s)')
    parser.add_argument("-n", "--instances", metavar="Number of instances", default="2", help="Create # Dispersy instances")
    parser.add_argument("-i", "--logging", metavar="Infologger", default="False", help="If True, logs will be shown in the cmd")
    args = parser.parse_args()
    
    num = int(args.instances)
    show_logs = True if args.logging == "True" else False;
    main(num, show_logs)
    
    
    
    
    
    