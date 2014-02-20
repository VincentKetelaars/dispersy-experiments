'''
Created on Nov 13, 2013

@author: Vincent Ketelaars
'''
import unittest
from src.download import Download
from dispersy.destination import CommunityDestination, CandidateDestination
from src.logger import get_logger
logger = get_logger(__name__)

class TestDownload(unittest.TestCase):


    def setUp(self):
        self.download = Download(None, None, None, None, None, None)

    def tearDown(self):
        del self.download
        
    def test_destination(self):
        candd = CandidateDestination()
        self.download._destination = candd
        self.assertFalse(self.download.candidate_destination())
        commd = CommunityDestination(2)
        self.download._destination = commd
        self.assertFalse(self.download.community_destination())

if __name__ == "__main__":
    unittest.main()