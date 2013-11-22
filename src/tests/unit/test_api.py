'''
Created on Nov 20, 2013

@author: Vincent Ketelaars
'''
import unittest
import os
import time

from threading import Event

from src.api import API
from src.tests.unit.definitions import DISPERSY_WORKDIR, FILES
from src.definitions import SWIFT_BINPATH, SLEEP_TIME, TIMEOUT_TESTS
from src.address import Address
from src.tests.unit.test_endpoint import remove_files

class TestAPI(unittest.TestCase):


    def setUp(self):
        self.workdir = DISPERSY_WORKDIR + "/temp"
        if not os.path.exists(self.workdir):
            os.makedirs(self.workdir)
        self.api1 = API(*(self.workdir, SWIFT_BINPATH),**{"walker":False})
        self.api2 = API(*(self.workdir, SWIFT_BINPATH),**{"walker":False})
        self.event = Event()
        self.files = FILES
        self.files_to_remove = []


    def tearDown(self):
        self.api1.stop()
        self.api2.stop()
        for f in self.files_to_remove:
            remove_files(f)
        
        
    def _wait(self, endpoint):
        for _ in range(int(TIMEOUT_TESTS / SLEEP_TIME)):
            check = True
            for d in endpoint.downloads.values():
                if not d.is_finished():
                    check = False
            if check and not len(endpoint.downloads) == 0:
                break
            time.sleep(SLEEP_TIME)


    def test_add_file_both(self):
        addr = Address(ip="127.0.0.1", port=12421)
        self.api1.start()
        self.api1.add_socket(addr)
        self.api2.start()
        self.api2.add_peer(addr)
        self.event.wait(1)
        self.api1.add_files([self.files[0]])
        self.api2.add_files([self.files[1]])
        self._wait(self.api1.dispersy_instance._dispersy.endpoint)
        file0 = os.path.join(self.workdir, os.path.basename(self.files[0]))
        file1 = os.path.join(self.workdir, os.path.basename(self.files[1]))
#         self.files_to_remove.append(file0)
#         self.files_to_remove.append(file1)
        self.assertTrue(os.path.exists(file0))
        self.assertTrue(os.path.exists(file1))


if __name__ == "__main__":
    unittest.main()