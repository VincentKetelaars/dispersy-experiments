'''
Created on Oct 9, 2013

@author: Vincent Ketelaars
'''

import Queue
from threading import Thread, Event

from src.logger import get_logger

logger = get_logger(__name__)
    
class CallFunctionThread(Thread):
    """
    Call function in separate thread.
    In case the queue has nothing to, the timeout will determine how long it waits for something to come up.
    """
    def __init__(self, daemon=True, timeout=1.0, name=""):
        Thread.__init__(self, name="CallFunctionThread_" + name)
        self.timeout = timeout
        self._run_event = Event() # Set when it is time to stop
        self.queue = Queue.PriorityQueue()        
        self.setDaemon(daemon)
        self.count = 0 # Number of Empty exceptions in a row
        self._task_available = Event() # Set if tasks are available
        self._done_event = Event() # Set when run is done
        self._wait_for_tasks = True # Allow new tasks and looping
        self._pause_event = Event()
        self._pause_event.set() # Default is not pausing
  
    def run(self):
        while not self._run_event.is_set() or (self._wait_for_tasks and not self.empty()):
            if self._task_available.is_set():
                try:
                    self._pause_event.wait()
                    _, (f, a, d) = self.queue.get()
                    f(*a, **d)
                    self.queue.task_done()                
                except Queue.Empty:
                    self._task_available.clear()
                except Exception:
                    logger.exception("")
            else:
                self._task_available.wait(self.timeout)
        self._done_event.set()
            
    def put(self, func, *args, **kargs):
        if not self._wait_for_tasks:
            return False
        self.queue.put((kargs.pop("queue_priority", None), (func, args, kargs)))
        self._task_available.set()
        return True
    
    def pause(self):
        self._pause_event.clear()
        
    def unpause(self):
        self._pause_event.set()
        
    def empty(self):
        return self.queue.empty()
        
    def queued(self):
        return self.queue.qsize()
    
    def stop(self, wait_for_tasks=False, timeout=1.0):
        self._wait_for_tasks = wait_for_tasks
        self._run_event.set() # Stop looping
        self._task_available.set() # Stop sleeping immediately
        if wait_for_tasks:
            self._done_event.wait(timeout) # Wait till nothing is left to do