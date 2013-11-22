'''
Created on Oct 9, 2013

@author: Vincent Ketelaars
'''

import Queue
from threading import Thread, Event

from dispersy.logger import get_logger

logger = get_logger(__name__)
    
class CallFunctionThread(Thread):
    """
    Call function in separate thread.
    In case the queue has nothing to, the timeout will determine how long it waits for something to come up.
    """
    def __init__(self, daemon=True, timeout=0.001):
        Thread.__init__(self)
        self.timeout = timeout
        self.event = Event()
        self.queue = Queue.Queue()        
        self.setDaemon(daemon)
        self.count = 0 # Number of Empty exceptions in a row
  
    def run(self):
        while not self.event.is_set():
            try:
                f, a, d = self.queue.get(True, self.timeout)
                f(*a, **d)
                self.queue.task_done()
            except Queue.Empty:    
                self.count += 1
            except Exception:
                self.count = 0
                logger.exception("Failed to run %s with %s %s", f, a, d)
            
    def put(self, func, args=(), kargs={}):
        self.queue.put((func, args, kargs))
    
    def stop(self):
        logger.debug("Stop with %d empty exceptions", self.count)
        self.event.set()