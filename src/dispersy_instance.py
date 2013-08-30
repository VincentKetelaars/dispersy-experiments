'''
Created on Aug 29, 2013

@author: Vincent Ketelaars
'''

import random

from os import getpid
from os.path import expanduser
from datetime import datetime

from dispersy.callback import Callback
from dispersy.endpoint import StandaloneEndpoint
from dispersy.dispersy import Dispersy
from dispersy.candidate import WalkCandidate

from src.extend.community import MyCommunity
from src.extend.endpoint import MultiEndpoint

import logging
logger = logging.getLogger()

class DispersyInstance(object):
    '''
    Instance of Dispersy that runs on its own process
    '''

    def _create_mycommunity(self):    
        master_member = self._dispersy.get_member(self._MASTER_MEMBER_PUBLIC_KEY)
        my_member = self._dispersy.get_new_member(self._SECURITY)
        return MyCommunity.join_community(self._dispersy, master_member, my_member)

    def __init__(self, conn):        
        self._SECURITY = u"medium"

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
        
        self._MASTER_MEMBER_PUBLIC_KEY = "307e301006072a8648ce3d020106052b81040024036a0004004b2c2fbbf036a0ae1dedf4420ff724869e324bc63064ec2e7bad062a7a9c7f31a7c3ff17a11fd582c9eb8b727dacb228afceb2002ad6e916efd4531e79f040341c7259c99938aae9f6ece17c5075b7ab8e9c92f7ff4493468d1e354a31d139e73928266b824fe3".decode("HEX")

        self._conn = conn        
        
    def run(self, num_instances):     
        # Create Dispersy object
        self._callback = Callback("MyDispersy")
        port1 = random.randint(10000, 20000)
    #     port2 = random.randint(10000, 20000)
        endpoint = MultiEndpoint()
        endpoint.add_endpoint(StandaloneEndpoint(port1))
    #     endpoint.add_endpoint(StandaloneEndpoint(port2))
        endpoint = StandaloneEndpoint(port1);
        
        dt = datetime.now()
        working_dir = expanduser("~") + u"/Music/"+ dt.strftime("%Y%m%d%H%M%S") + "_" + str(getpid()) + "/"
        sqlite_database = working_dir + unicode(port1)
    #     sqlite_database = u":memory:"
        self._dispersy = Dispersy(self._callback, endpoint, working_dir, sqlite_database)
        
        self._dispersy.start()
        print "Dispersy is listening on port %d" % self._dispersy.lan_address[1]
        
        self._community = self._callback.call(self._create_mycommunity)
        
        # At some point kill the self._connection
        self._conn.send(self._dispersy.lan_address)
        
        for _ in range(num_instances-1):
            address = self._conn.recv()
            self._callback.call(self._dispersy.create_introduction_request, (self._community,WalkCandidate(address, False, address, address, u"unknown"),True,True))
            
        self._loop()
        
        self._stop()
        
    def _register_some_message(self, message=None, count=1, delay=5.0):
        logger.info("Registered %d messages: %s with delay %f", count, message, delay)
        self._callback.register(self._community.create_my_messages, (count,message), delay=delay)        
        
    def _loop(self):
        self._continue = True
        
        options = {"message" : self._register_some_message,
                   "continue" : self._set_continue}
        
        while self._continue:
            if self._conn.poll(0.5):
                kind = self._conn.recv()
                value = self._conn.recv()
                options[kind](value)
    
    def _set_continue(self, _continue):
        self._continue = _continue
    
    def _stop(self):
        self._conn.close()
        self._dispersy.stop()