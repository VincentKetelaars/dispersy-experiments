'''
Created on Jan 7, 2014

@author: Vincent Ketelaars
'''
from dispersy.dispersy import Dispersy

from src.dispersy_extends.community import MyCommunity
from src.logger import get_logger
logger = get_logger(__name__)

class MyDispersy(Dispersy):

    def on_swift_restart(self, q, roothashes):
        """
        When a Swift instance fails, a new instance is created. 
        This new instance needs to be notified of its downloads and peers.
        This method asks each SwiftCommunity to add endpoint functions to the queue.
        q.put((func, (args), {kwargs}))
        """
        for c in self._communities.itervalues():
            if isinstance(c, MyCommunity):
                c.swift_community.put_endpoint_calls(q, roothashes)