'''
Created on Nov 15, 2013

@author: Vincent Ketelaars
'''

import Queue
from threading import Thread


from src.dispersy_instance import DispersyInstance
from src.address import Address
from src.definitions import STATE_RUNNING

from dispersy.logger import get_logger
logger = get_logger(__name__)

class API(Thread):
    '''
    Command Gateway is a separate thread which will be take commands from another process connected to the pipe.
    '''

    def __init__(self, *di_args, **di_kwargs):
        Thread.__init__(self)
        self.setDaemon(True)  # Automatically die when the main thread dies
        self.dispersy_instance = DispersyInstance(*di_args, **di_kwargs)
        self.dispersy_instance.set_callback(self._generic_callback)
        self._queue = Queue.Queue()
        
    def run(self):
        logger.debug("Started DispersyInstance")
        self.dispersy_instance.start() # This is blocking
        logger.debug("Dispersy has ended")
    
    @property
    def state(self):
        return self.dispersy_instance.state
        
    def stop(self):
        return self.dispersy_instance.stop()
        
    def add_message(self, message):
        assert len(message) < 2**16
        if self.state == STATE_RUNNING:
            pass
        # TODO: These will be special message kinds which need to be developed..
    
    def monitor_directory_for_files(self, directory):
        if self.state == STATE_RUNNING:
            return self.dispersy_instance._filepusher.set_directory(directory)
        else:
            self._enqueue(self.monitor_directory_for_files, (directory,), {})
        
    def add_files(self, files):
        if self.state == STATE_RUNNING:
            return self.dispersy_instance._filepusher.add_files(files)
        else:
            self._enqueue(self.add_files, (files,), {})
    
    def add_peer(self, address):
        assert isinstance(address, Address)
        if self.state == STATE_RUNNING:
            self.dispersy_instance.send_introduction_request(address.addr())
        else:
            self._enqueue(self.add_peer, (address,), {})
        
    def add_socket(self, address):
        assert isinstance(address, Address)
        if self.state == STATE_RUNNING:
            e = self.dispersy_instance._endpoint.add_endpoint(address)
            e.open(self.dispersy_instance._dispersy)
        else:
            self._enqueue(self.add_socket, (address,), {})
    
    def return_progress_data(self):
        if self.state == STATE_RUNNING:
            downloads = self.dispersy_instance._endpoint.downloads
        else:
            self._enqueue(self.return_progress_data, (), {})
        # These downloads should contain most information
        # TODO: Find something to return
    
    def interface_came_up(self, ip, if_name, device):
        addr = Address.unknown(ip)
        if addr.resolve_interface():
            if addr.interface.name != if_name:
                return # Provided the wrong interface..
            else:
                addr.interface.device = device
        if self.state == STATE_RUNNING:
            return self.dispersy_instance._endpoint.if_came_up(addr)
        else:
            self._enqueue(self.interface_came_up, (ip, if_name, device), {})
        
    def set_API_logger(self, logger):
        logger = logger
        
    def set_dispersy_instance_logger(self, logger):
        pass
    
    def _generic_callback(self, name, args=(), kwargs={}):
        logger.debug("Callback %s %s %s", name, args, kwargs)
        if name == "state":
            return self._state_callback(*args, **kwargs)
            
    def _state_callback(self, state):
        if state == STATE_RUNNING:
            self._dequeue()
            
    def _enqueue(self, func, args, kwargs):
        logger.debug("Enqueue %s %s %s", func, args, kwargs)
        self._queue.put((func, args, kwargs))
    
    def _dequeue(self):
        while not self._queue.empty() and self.state == STATE_RUNNING:
            func, args, kwargs = self._queue.get()
            logger.debug("Dequeue %s %s %s", func, args, kwargs)
            func(*args, **kwargs)
    
    
