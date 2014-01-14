'''
Created on Sep 17, 2013

@author: Vincent Ketelaars
'''
import unittest

from src.logger import get_logger
from dispersy.candidate import Candidate

from src.tests.unit.definitions import SMALL_TASK_TIMEOUT
from src.dispersy_instance import DispersyInstance
from src.definitions import SWIFT_BINPATH, DEST_DIR, FILE_HASH_MESSAGE_NAME, SMALL_FILE_MESSAGE_NAME,\
    ADDRESSES_MESSAGE_NAME, API_MESSAGE_NAME
from src.dispersy_extends.conversion import FileHashConversion, SmallFileConversion, AddressesConversion,\
    APIMessageConversion
from src.address import Address

logger = get_logger(__name__)

class TestConversion(unittest.TestCase):
    
    def setUp(self):
        self._di = DispersyInstance(DEST_DIR, SWIFT_BINPATH, run_time=SMALL_TASK_TIMEOUT)
        self._di.start()
        self._conversions = self._di._community._conversions

    def tearDown(self):
        self._di.stop()
                
    def test_file_hash_message_conversion(self):
        for c in self._conversions:
            if isinstance(c, FileHashConversion):
                meta = self._di._community.get_meta_message(FILE_HASH_MESSAGE_NAME)
                filename = "asdf.asdf"
                dir_ = ""
                roothash = "asdfj23j09f09sjfewef"
                address = Address.ipv4("0.0.0.0:1")
                message = meta.impl(authentication=(self._di._community.my_member,), distribution=(self._di._community.claim_global_time(), self._di._community._file_hash_distribution.claim_sequence_number()), 
                              payload=(filename, dir_, roothash, [address]))
                encoded = c.encode_payload(message)
                placeholder = c.Placeholder(None, meta, 0, encoded, False, True)
                _, x = c.decode_payload(placeholder, 0, str(encoded[0])+encoded[1])
                self.assertEqual(x.filename, filename)
                self.assertEqual(x.directories, dir_)
                self.assertEqual(x.roothash, roothash)
                self.assertEqual(x.addresses[0], address)
                
    def test_small_file_message_conversion(self):
        for c in self._conversions:
            if isinstance(c, SmallFileConversion):
                meta = self._di._community.get_meta_message(SMALL_FILE_MESSAGE_NAME)
                filename = "asdf.asdf"
                data = "asjfdioewf"
                message = meta.impl(authentication=(self._di._community.my_member,), distribution=(self._di._community.claim_global_time(), self._di._community._file_hash_distribution.claim_sequence_number()), 
                              payload=(filename, data))
                encoded = c.encode_payload(message)
                placeholder = c.Placeholder(None, meta, 0, encoded, False, True)
                _, x = c.decode_payload(placeholder, 0, str(encoded[0])+encoded[1])
                self.assertEqual(x.filename, filename)
                self.assertEqual(x.data, data)
                
    def test_addresses_message_conversion(self):
        for c in self._conversions:
            if isinstance(c, AddressesConversion):
                meta = self._di._community.get_meta_message(ADDRESSES_MESSAGE_NAME)
                addresses = [Address.ipv4("0.0.0.1:1232"), Address.ipv6("[::0]:12145"), Address(port=32532)]
                message = meta.impl(authentication=(self._di._community.my_member,),
                                      distribution=(self._di._community.claim_global_time(),),
                                      destination=(Candidate(addresses[0].addr(), True),), 
                                      payload=(addresses,))
                encoded = c.encode_payload(message)
                placeholder = c.Placeholder(None, meta, 0, encoded, False, True)
                _, x = c.decode_payload(placeholder, 0, str(encoded[0])+encoded[1])
                self.assertEqual(x.addresses, addresses)
                
    def test_uav_message_conversion(self):
        for c in self._conversions:
            if isinstance(c, APIMessageConversion):
                meta = self._di._community.get_meta_message(API_MESSAGE_NAME)
                data = "asjfdioewf"
                addresses = [Address.ipv4("0.0.0.1:1232"), Address.ipv6("[::0]:12145"), Address(port=32532)]
                message = meta.impl(authentication=(self._di._community.my_member,),
                                      distribution=(self._di._community.claim_global_time(),),
                                      destination=(Candidate(addresses[0].addr(), True),), 
                                      payload=(data,))
                encoded = c.encode_payload(message)
                placeholder = c.Placeholder(None, meta, 0, encoded, False, True)
                _, x = c.decode_payload(placeholder, 0, str(encoded[0])+encoded[1])
                self.assertEqual(x.message, data)

if __name__ == "__main__":
    unittest.main()