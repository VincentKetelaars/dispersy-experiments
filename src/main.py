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

from dispersy.crypto import ec_generate_key, ec_signature_length, ec_to_private_bin, ec_to_public_bin
from dispersy.callback import Callback
from dispersy.endpoint import StandaloneEndpoint
from dispersy.dispersy import Dispersy

from src.community import MyCommunity
from src.extend.callback import MyCallback

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

def get_mycommunity(dispersy, master_member):
    return MyCommunity.load_community(dispersy, master_member)

def single_callback_multiple_dispersy():
    # Create Dispersy object
    callback = MyCallback("MyDispersy")
    dt = datetime.now()
    database_path = expanduser("~") + u"/Music/Multi/" + dt.strftime("%Y%m%d%H%M%S") # Create unique place for database
    
    endpoint1 = StandaloneEndpoint(random.randint(10000, 20000))
    dispersy1 = Dispersy(callback, endpoint1, database_path)        
    
    endpoint2 = StandaloneEndpoint(random.randint(10000, 20000))
    dispersy2 = Dispersy(callback, endpoint2, database_path) # Multiple instances, same database gives errors?
    
    dispersy1.start()
    print "Dispersy1 is listening on port %d" % dispersy1.lan_address[1]
    
    dispersy2.start()
    print "Dispersy2 is listening on port %d" % dispersy2.lan_address[1]
    
    # Two different communities with same master_member and only one member
    community1 = callback.call(create_mycommunity, (dispersy1,))
    community2 = callback.call(get_mycommunity, (dispersy2, community1.master_member))
    
    callback.register(community1.create_my_messages, (1,), delay=1.0)
    
    try:
        time.sleep(5)
    except:
        pass
    finally:
        dispersy1.stop()
        dispersy2.stop() # Somewhere in callback._loop something goes wrong
        
def single_callback_single_dispersy():
    # Create Dispersy object
    callback = Callback("MyDispersy")
    port = random.randint(10000, 20000)
    endpoint = StandaloneEndpoint(port)
    dispersy = Dispersy(callback, endpoint, expanduser("~") + u"/Music/"+unicode(port)) # Multiple instances, same database gives errors?
    
    dispersy.start()
    print "Dispersy is listening on port %d" % dispersy.lan_address[1]
    
    community = callback.call(create_mycommunity, (dispersy,))
    callback.register(community.create_my_messages, (1,), delay=5.0)
    
    try:
        time.sleep(30)
    except:
        pass
    finally:
        dispersy.stop()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Start Dispersy instance(s)')
    parser.add_argument("-s", "--single", metavar="Single dispersy instance", default="True", help='If True only one dispersy instance for each callback, false otherwise')
    parser.add_argument("-i", "--info", metavar="Infologger", default="False", help="If True, Info logs will be shown in the cmd")
    args = parser.parse_args()
    
    # Why show only INFO?
    if (args.info == "True"):
        logger_conf = os.path.abspath(os.environ.get("LOGGER_CONF", "logger.conf"))
        print "Logger using configuration file: " + logger_conf
        logging.config.fileConfig(logger_conf)
        logger = logging.getLogger(__name__)
        
    if (args.single == "True"):
        single_callback_single_dispersy()
    else:
        single_callback_multiple_dispersy()
    
    
    
    