'''
Created on Nov 21, 2013

@author: Vincent Ketelaars
'''

from datetime import datetime
import collections
from src.download import Peer
from src.address import Address

class DispersyContact(object):
    '''
    This object represents a Dispersy contact (i.e. peer address). 
    Each incoming and outgoing message to this address is noted.
    '''

    def __init__(self, address, send_messages=[], recv_messages=[]):
        self.address = address # Primary address
        self.last_send_time = {address : datetime.min}
        self.last_recv_time = {address : datetime.min}
        self.count_send = {}
        self.count_recv = {}
        self.peer = Peer([address])
        if send_messages: # not []
            self.send(send_messages)
        if recv_messages: # not []
            self.recv(recv_messages)
       
    def recv(self, messages, address=Address()):
        assert isinstance(messages, collections.Iterable)
        self.count_recv[address] = self.count_recv.get(address, 0) + len(messages)
        self.last_recv_time[address] = datetime.utcnow()
        
    def total_received(self):
        return sum([v for k, v in self.count_recv.items() if k in self.peer.addresses])
        
    def send(self, messages, address=Address()):
        assert isinstance(messages, collections.Iterable)
        self.count_send[address] = self.count_send.get(address, 0) + len(messages)
        self.last_send_time[address] = datetime.utcnow()
        
    def total_send(self):
        return sum([v for k, v in self.count_send.items() if k in self.peer.addresses])
        
    def last_contact(self, address=None):
        """
        This function returns the last time there was either a send or a receive to or from the supplied address
        If no address is supplied, the default address will be used
        @return the last contact, otherwise datetime.min
        """
        if address is None:
            return max(self.last_send_time[self.address], self.last_recv_time[self.address])
        return max(self.last_send_time.get(address, datetime.min), self.last_recv_time.get(address, datetime.min))
    
    def set_peer(self, peer):
        """
        @type peer: Peer
        """
        self.peer = peer
        
    def has_address(self, address):
        """
        Return whether this address belongs to this contact
        @type address: Address
        """
        return address == self.address or (self.peer is not None and self.peer.has_any([address]))
        
    # We only care about the address when comparing
    def __eq__(self, other):
        if not isinstance(other, DispersyContact):
            return False
        if self.address == other.address:
            return True
        return False
        
    def __ne__(self, other):
        return not self.__eq__(other)
    
    # Create this hash function to make it easily comparible in a set..
    # The address should be the key
    # We do not use peer because we rely on the user to ensure that the same peer does not get multiple DispersyContacts
    def __hash__(self, *args, **kwargs):
        return hash(self.address)