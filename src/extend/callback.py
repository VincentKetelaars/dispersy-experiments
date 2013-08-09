'''
Created on Aug 9, 2013

@author: Vincent Ketelaars
'''

from dispersy.callback import Callback
from threading import Thread
from time import sleep

class MyCallback(Callback):
    '''
    classdocs
    '''

    def start(self, wait=True):
        """
        Start the asynchronous thread.

        Creates a new thread and calls the _loop() method.
        """
                            
        if not self.is_running:
            with self._lock:
                self._state = "STATE_PLEASE_RUN"
            
            thread = Thread(target=self._loop, name=self._name)
            thread.daemon = True
            thread.start()
        else:
            wait=False
        
        if wait:
            # Wait until the thread has started
            while self._state == "STATE_PLEASE_RUN":
                sleep(0.01)

        return self.is_running
        