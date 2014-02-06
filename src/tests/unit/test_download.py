'''
Created on Nov 13, 2013

@author: Vincent Ketelaars
'''
import unittest
from socket import AF_INET6

from src.download import Download, Peer
from src.address import Address
from dispersy.destination import CommunityDestination, CandidateDestination
from dispersy.candidate import WalkCandidate
from src.logger import get_logger
logger = get_logger(__name__)

class TestDownload(unittest.TestCase):


    def setUp(self):
        self.download = Download(None, None, None, None, None)
        self.address1 = Address(port=123)
        self.address2 = Address(ip="12.23.34.45", port=1234)
        self.address3 = Address(ip="0.0.1.2", port=1234)

    def tearDown(self):
        del self.download

    def test_merge_peer_community(self):
        self.download._seed = True
        self.download.determine_seeding()
        commd = CommunityDestination(2)
        self.download._destination = commd.implement()
        peer1 = Peer([self.address1])
        peer2 = Peer([self.address2, self.address3])
        peer3 = Peer([self.address1, self.address2])
        self.download.add_peer(peer1)
        self.assertIn(peer1, self.download.peers())
        self.assertEqual(len(self.download.peers()), 1)
        self.download.add_peer(peer2)
        self.assertIn(peer2, self.download.peers())
        self.assertEqual(len(self.download.peers()), 2)
        self.download.merge_peers(peer3)
        self.assertIn(peer3, self.download.peers())
        self.assertEqual(len(self.download.peers()), 1)
        self.assertEqual(self.download.allowed_addresses(), None)
        self.assertTrue(self.download.known_address(self.address1))
        self.assertTrue(self.download.known_address(self.address2))
        self.assertTrue(self.download.known_address(self.address3))
        
    def candidate(self, addr):
        return WalkCandidate(addr, True, addr, addr, u"unknown")
        
    def test_merge_peer_candidate(self):
        self.download._seed = True
        self.download.determine_seeding()
        peer1 = Peer([self.address1])
        peer2 = Peer([self.address2, self.address3])
        peer3 = Peer([self.address1, self.address2])
        candd = CandidateDestination()
        self.download._destination = candd.implement(self.candidate(self.address1.addr()))
        logger.debug(self.download._destination.candidates)
        self.download.add_peer(peer1)
        self.assertIn(peer1, self.download.peers())
        self.assertEqual(len(self.download.peers()), 1)
        self.download.add_peer(peer2) # Not in CandidateDestination.Implementation
        self.assertNotIn(peer2, self.download.peers())
        self.assertEqual(len(self.download.peers()), 1)
        self.download.merge_peers(peer3)
        self.assertIn(peer3, self.download.peers())
        self.assertEqual(len(self.download.peers()), 1)
        self.assertEqual(len(self.download.allowed_addresses()), 1)
        self.assertTrue(self.download.known_address(self.address1))
        self.assertTrue(self.download.known_address(self.address2))
        self.assertFalse(self.download.known_address(self.address3))
        
    def test_destination(self):
        candd = CandidateDestination()
        self.download._destination = candd
        self.assertFalse(self.download.candidate_destination())
        commd = CommunityDestination(2)
        self.download._destination = commd
        self.assertFalse(self.download.community_destination())

class TestPeer(unittest.TestCase):
    
    def test_peer_equal(self):
        self.assertEqual(Peer([Address(ip="0.1.2.3", port=4235), Address(ip="0.1.2.6", port=42356)]),
                         Peer([Address(ip="0.1.2.3", port=4235), Address(ip="0.1.2.6", port=42356)]))

if __name__ == "__main__":
    unittest.main()