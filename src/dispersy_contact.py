'''
Created on Nov 21, 2013

@author: Vincent Ketelaars
'''

from datetime import datetime, timedelta
from src.download import Peer
from src.address import Address

from src.logger import get_logger
from src.definitions import ENDPOINT_CONTACT_TIMEOUT
logger = get_logger(__name__)

class DispersyContact(object):
    '''
    This object represents a Dispersy contact (i.e. peer address). 
    Each incoming and outgoing message to this address is noted.
    '''

    def __init__(self, address, sent_messages=0, sent_bytes=0, rcvd_messages=0, rcvd_bytes=0, community_id=None):
        self.address = address # Primary address
        self.last_send_time = {address : datetime.min}
        self.last_recv_time = {address : datetime.min}
        self.count_sent = {}
        self.count_rcvd = {}
        self.bytes_sent = {}
        self.bytes_rcvd = {}
        self.community_ids = set([community_id]) if community_id is not None else set()
        self.peer = Peer([address])
        if sent_messages > 0:
            self.sent(sent_messages, sent_bytes, address=address)
        if rcvd_messages > 0:
            self.rcvd(rcvd_messages, rcvd_bytes, address=address)
       
    def rcvd(self, num_messages, bytes_rcvd, address=Address()):
        self.count_rcvd[address] = self.count_rcvd.get(address, 0) + num_messages
        self.bytes_rcvd[address] = self.bytes_rcvd.get(address, 0) + bytes_rcvd
        self.last_recv_time[address] = datetime.utcnow()
        
    def num_rcvd(self):
        return sum([v for k, v in self.count_rcvd.items() if k in self.peer.addresses])
    
    def total_rcvd(self):
        return sum([v for k, v in self.bytes_rcvd.items() if k in self.peer.addresses])
        
    def sent(self, num_messages, bytes_sent, address=Address()):
        self.count_sent[address] = self.count_sent.get(address, 0) + num_messages
        self.bytes_sent[address] = self.bytes_sent.get(address, 0) + bytes_sent
        self.last_send_time[address] = datetime.utcnow()
        
    def num_sent(self):
        return sum([v for k, v in self.count_sent.items() if k in self.peer.addresses])
    
    def total_sent(self):
        return sum([v for k, v in self.bytes_sent.items() if k in self.peer.addresses])
        
    def last_contact(self, address=None):
        """
        This function returns the last time there was either a send or a receive to or from the supplied address
        If no address is supplied, the default address will be used
        @return the last contact, otherwise datetime.min
        """
        if address is None:
            return max(self.last_send_time[self.address], self.last_recv_time[self.address])
        return max(self.last_send_time.get(address, datetime.min), self.last_recv_time.get(address, datetime.min))
    
    def no_contact_since(self, expiration_time=ENDPOINT_CONTACT_TIMEOUT):
        addrs = []
        for a in self.peer.addresses:
            if (self.last_recv_time.get(a, datetime.min) + timedelta(seconds=expiration_time) < datetime.utcnow() or
                self.last_send_time.get(a, datetime.min) + timedelta(seconds=expiration_time) < datetime.utcnow()): # Timed out
                addrs.append(a)
        return addrs
    
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
    
    def merge(self, contact):
        self.merge_stats(contact)
        self.community_ids.update(contact.community_ids)
    
    def merge_stats(self, contact):
        """
        Merge statistics of this contact with that of another DispersyContact
        @type contact: DispersyContact
        """
        assert (contact, DispersyContact)
        for k, v in contact.last_send_time.iteritems():
            self.last_send_time[k] = max(self.last_send_time.get(k, datetime.min), v)
        for k, v in contact.last_recv_time.iteritems():
            self.last_recv_time[k] = max(self.last_recv_time.get(k, datetime.min), v)
        for k, v in contact.count_sent.iteritems():
            self.count_sent[k] = self.count_sent.get(k, 0) + v
        for k, v in contact.bytes_sent.iteritems():
            self.bytes_sent[k] = self.bytes_sent.get(k, 0) + v
        for k, v in contact.count_rcvd.iteritems():
            self.count_rcvd[k] = self.count_rcvd.get(k, 0) + v
        for k, v in contact.bytes_rcvd.iteritems():
            self.bytes_rcvd[k] = self.bytes_rcvd.get(k, 0) + v
            
    def addr_info(self, address):
        return "%d:%d rcvd at %s, %d:%d sent %s" % (self.count_rcvd.get(address, 0), self.bytes_rcvd.get(address, 0), 
                                                    self.last_recv_time.get(address, datetime.min), self.count_sent.get(address, 0),
                                                    self.bytes_sent.get(address, 0), self.last_send_time.get(address, datetime.min))
            
    def __str__(self):
        return "%s, %d:%d sent, %d:%d received, at %s" % (self.address, self.num_sent(), self.total_sent(), 
                                                          self.num_rcvd(), self.total_rcvd(), self.last_contact())
        
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