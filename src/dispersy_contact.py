'''
Created on Nov 21, 2013

@author: Vincent Ketelaars
'''

from datetime import datetime
import collections

class DispersyContact(object):
    '''
    This object represents a Dispersy contact (i.e. peer address). 
    Each incoming and outgoing message to this address is noted.
    '''

    def __init__(self, address, send_messages=[], recv_messages=[]):
        self.address = address # Primary address
        self.last_send_time = datetime.min
        self.last_recv_time = datetime.min
        self.count_send = 0
        self.count_recv = 0
        self.peer = None
        if send_messages: # not []
            self.send(send_messages)
        if recv_messages: # not []
            self.recv(recv_messages)
       
    def recv(self, messages):
        assert isinstance(messages, collections.Iterable)
        self.count_recv += len(messages)
        self.last_recv_time = datetime.utcnow()
        
    def send(self, messages):
        assert isinstance(messages, collections.Iterable)
        self.count_send += len(messages)
        self.last_send_time = datetime.utcnow()
        
    def last_contact(self):
        """
        This function returns the last time there was either a send or a receive to or from this peer address
        If there has been no contact it returns None
        @return the last contact, otherwise datetime.min
        """
        return max(self.last_send_time, self.last_recv_time)
    
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