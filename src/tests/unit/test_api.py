'''
Created on Nov 20, 2013

@author: Vincent Ketelaars
'''
import unittest
import os
import re
from threading import Event

from src.logger import get_logger

from src.api import API
from src.tests.unit.definitions import DISPERSY_WORKDIR, FILES, TIMEOUT_TESTS
from src.definitions import SWIFT_BINPATH, STATE_RESETTING
from src.address import Address
from src.tests.unit.test_endpoint import remove_files

logger = get_logger(__name__)

class TestAPI(unittest.TestCase):
    
    class MyAPI(API):
        
        def __init__(self, name, *di_args, **di_kwargs):
            API.__init__(self, name, *di_args, **di_kwargs)
            self.fails = 0
            self._run_event = Event()
            self.files_done = 0
            self._done_event = Event()
            self.message = None
        
        def socket_state_callback(self, addr, state):
            if state > 0:
                self.fails += 1
                self._run_event.set()       
        
        def file_received_callback(self, file_):
            self.files_done += 1
            self._run_event.set()
            
        def message_received_callback(self, message):
            self.message = message
            self._run_event.set()
            
        def finish(self):
            API.finish(self)
            self._done_event.set()

    def setUp(self):
        self.workdir = DISPERSY_WORKDIR + "/temp"
        if not os.path.exists(self.workdir):
            os.makedirs(self.workdir)
        self.workdir2 = DISPERSY_WORKDIR + "/temp2"
        if not os.path.exists(self.workdir2):
            os.makedirs(self.workdir2)
        self.api1 = self.MyAPI("API1", self.workdir, SWIFT_BINPATH, walker=False)
        self.files = FILES
        self.files_to_remove = []


    def tearDown(self):
        self.api1.stop()
        try:
            self.api2.stop() # Only necessary when test creates this second api
        except AttributeError:
            pass
        self.api1._done_event.wait(2)
        try:
            self.api2._done_event.wait(2)
        except AttributeError:
            pass
        for f in self.files_to_remove:
            remove_files(f, True)
        for f in FILES:
            remove_files(f, False)

    def test_add_file_both(self):
        self.api2 = self.MyAPI("API2", self.workdir2, SWIFT_BINPATH, walker=False, listen=[Address(ip="127.0.0.1")])        
        
        addr = Address(ip="127.0.0.1", port=12421)
        self.api1.start()
        self.api1.add_socket(addr.ip, addr.port, addr.family)
        self.api2.start()
        self.api2.add_peer(addr.ip, addr.port, addr.family)
        
        self.api1.add_file(self.files[0])
        self.api2.add_file(self.files[1])
        file0 = os.path.join(self.workdir2, os.path.basename(self.files[0]))
        file1 = os.path.join(self.workdir, os.path.basename(self.files[1]))
        self.files_to_remove.append(file0)
        self.files_to_remove.append(file1)
        
        self.api1._run_event.wait(TIMEOUT_TESTS / 2)
        self.api2._run_event.wait(TIMEOUT_TESTS / 2)
        
        self.assertTrue(os.path.exists(file0))
        self.assertTrue(os.path.exists(file1))
        
    def test_add_socket_if_came_up_and_process_unstarted(self):
        address = Address(ip="127.0.0.1", port=12345)

        self.api1.add_socket(address.ip, address.port, address.family)
        self.api1.interface_came_up(address.ip, "lo", "lo", gateway="127.0.0.1")
        self.api1.start()
        
        self.api1._run_event.wait(2) # Should be plenty of time
        self.assertEqual(self.api1.fails, 0)
        
    def test_api_message(self):
        addr = Address(ip="127.0.0.1", port=12421)
        self.api2 = self.MyAPI("API2", self.workdir2, SWIFT_BINPATH, walker=False, 
                               listen=[Address(ip="127.0.0.1")], peers=[addr], bloomfilter_update=2)        
        
        self.api1.start()
        self.api1.add_socket(addr.ip, addr.port, addr.family)
        self.api2.start()
        message = "Something cool"
        self.api2.add_message(message)
        
        self.api1._run_event.wait(4)
        
        self.assertEqual(message, self.api1.message)
        
class TestAPINetworkInterface(unittest.TestCase):
    
    class MyWifiAPI(API):
        
        def __init__(self, name, *di_args, **di_kwargs):
            API.__init__(self, name, *di_args, **di_kwargs)
            self._run_event = Event()
            self.sock_states = []
            
        def run(self):
            ip = "193.156.108.78"
            port = 0
            self.add_socket(ip, port)
            self.add_peer(ip, 12346)
            event = Event()
            event.wait(2)
            if_ = "wlan0"
            os.system("ifconfig %s down" % if_)
            event.wait(25)
            while True:
                output = os.popen('ifconfig').read()
                index = output.find(if_)
                if index > 0:
                    wlan_config = output[index:]
                    m = re.search("inet addr:(\d+\.\d+\.\d+\.\d+)", wlan_config, re.IGNORECASE)
                    if m:
                        ip = m.groups()[0]
                    self.interface_came_up(ip, if_, if_[0:-1], None)
                    break
                event.wait(1)
            event.wait(1)
            self._run_event.set()       
        
        def socket_state_callback(self, socket, state):
            self.sock_states.append(state)
    
    def setUp(self):
        self.workdir = DISPERSY_WORKDIR + "/temp"
        if not os.path.exists(self.workdir):
            os.makedirs(self.workdir)
        self.api = self.MyWifiAPI("myapi", self.workdir, SWIFT_BINPATH, walker=True)


    def tearDown(self):
        if self.api:
            self.api.stop()
        
    def test_wifi_up_down(self):       
        self.restarted = False
        def restart_callback(state, error=None):
            if state == STATE_RESETTING:
                self.restarted = True
        
        self.api.swift_state_callback(restart_callback)
        self.api.start()
        
        self.api._run_event.wait(40)
        
        self.assertFalse(self.restarted)
        self.assertGreater(len(self.api.sock_states), 0) # Test so that the next one cannot give an error
        self.assertEqual(self.api.sock_states[0], 0) # Should be okay first
        self.assertEqual(self.api.sock_states[-1], 0) # Last should be okay also
        
if __name__ == "__main__":
    unittest.main()