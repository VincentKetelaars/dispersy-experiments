'''
Created on Sep 17, 2013

@author: Vincent Ketelaars
'''
import unittest

from dispersy.callback import Callback
from dispersy.conversion import Conversion

from src.definitions import MASTER_MEMBER_PUBLIC_KEY, SECURITY
from src.dispersy_extends.community import MyCommunity
from src.dispersy_extends.mydispersy import MyDispersy
from src.tests.unit.mock_classes import FakeCommonEndpoint

class TestMyCommunity(unittest.TestCase):
    
    def setUp(self):
        callback = Callback("TestCallback")
        endpoint = FakeCommonEndpoint(None)
        self._dispersy = MyDispersy(callback, endpoint, u".", u":memory:")
        self._dispersy.start()
        master = callback.call(self._dispersy.get_member, (MASTER_MEMBER_PUBLIC_KEY,))
        my_member = callback.call(self._dispersy.get_new_member,(SECURITY,))
        self._community = callback.call(MyCommunity.join_community, (self._dispersy, master, my_member))

    def tearDown(self):
        self._dispersy.stop()
    
    def test_initiate_conversions(self):
        conversions = self._community.initiate_conversions()
        self.assertTrue(len(conversions) >= 1)
        for c in conversions:
            self.assertIsInstance(c, Conversion)
        
if __name__ == "__main__":
    unittest.main()