'''
Created on Oct 9, 2013

@author: Vincent Ketelaars
'''

import Queue
from threading import Thread, Event
    
class CallFunctionThread(Thread):
    """
    Call function in separate thread.
    """
    def __init__(self, timeout=0.0):
        Thread.__init__(self)
        self.timeout = timeout
        self.event = Event()
        self.queue = Queue.Queue()        
        self.daemon = True
  
    def run(self):
        while not self.event.is_set():
            try:
                f, a, d = self.queue.get(True, self.timeout)
                f(*a, **d)
                self.queue.task_done()
            except:
                pass
            
    def put(self, func, args=(), kargs={}):
        self.queue.put((func, args, kargs))
        
    def stop(self):
        if not self.event.is_set():
            self.event.set()
        self.join()
        
    
        