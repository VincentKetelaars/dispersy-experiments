'''
Created on Nov 13, 2013

@author: Vincent Ketelaars
'''
import unittest

from src.download import Download, Peer
from src.address import Address

class TestDownload(unittest.TestCase):


    def setUp(self):
        self.download = Download(None, None, None)
        self.address1 = Address(port=123)
        self.address2 = Address(ip="::1", port=1234)
        self.address3 = Address(ip="0.0.1.2", port=1234)

    def tearDown(self):
        del self.download

    def test_merge_peer(self):
        peer1 = Peer([self.address1])
        peer2 = Peer([self.address2, self.address3])
        peer3 = Peer([self.address1, self.address2])
        self.download.add_peer(peer1)
        self.assertTrue(peer1 in self.download.peers())
        self.assertEqual(len(self.download.peers()), 1)
        self.download.add_peer(peer2)
        self.assertTrue(peer2 in self.download.peers())
        self.assertEqual(len(self.download.peers()), 2)
        self.download.merge_peers(peer3)
        self.assertTrue(peer3 in self.download.peers())
        self.assertEqual(len(self.download.peers()), 1)
        

class TestPeer(unittest.TestCase):
    
    def test_peer_equal(self):
        self.assertEqual(Peer([Address(ip="0.1.2.3", port=4235), Address(ip="0.1.2.6", port=42356)]),
                         Peer([Address(ip="0.1.2.3", port=4235), Address(ip="0.1.2.6", port=42356)]))

if __name__ == "__main__":
    unittest.main()