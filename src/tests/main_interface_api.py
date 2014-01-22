'''
Created on Jan 22, 2014

@author: Vincent Ketelaars
'''
import re
import os
from threading import Event

from src.api import API
from src.logger import get_logger
logger = get_logger(__name__)

class MainInterfaceAPI(API):
        
    def __init__(self, name, *di_args, **di_kwargs):
        API.__init__(self, name, *di_args, **di_kwargs)
        self._need_socket_event = Event()
        self._running = Event()
        
    def _find(self, _input, _format, default):
        m = re.search(_format, _input, re.IGNORECASE)
        if m:
            return m.groups()[0]
        return default
    
    def run(self):
        
        while not self._running.is_set():
            if not self._need_socket_event.is_set():
                output = os.popen('ip route').read()
                ip = self._find(output, "src (\d+\.\d+\.\d+\.\d+)", None)
                if_name = self._find(output, "dev ([a-zA-Z]{3,4}\d)", None)
                gateway = self._find(output, "default via (\d+\.\d+\.\d+\.\d+)", None)
                if ip is not None:
                    self.interface_came_up(ip, if_name, if_name[0:-1] if not if_name is None else None, gateway)
            self._running.wait(1)
        
    def socket_state_callback(self, socket, state):
        if state == 0 or state == 11:
            self._need_socket_event.set()
        else:
            self._need_socket_event.clear()
            
if __name__ == "__main__":
    from src.main import main
    args, kwargs = main()
    a = MainInterfaceAPI("MainInterfaceAPI", *args, **kwargs)
    a.start()