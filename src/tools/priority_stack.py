'''
Created on Feb 19, 2014

@author: Vincent Ketelaars
'''
from src.logger import get_logger
logger = get_logger(__name__)

class PriorityStack(object):
    '''
    This class represents a stack where input is prioritized by a single parameter
    Note that that parameter can also be a tuple, effectively allowing for multiple parameters
    where the first is the primary priority.
    '''

    def __init__(self):
        self._stack = [] # (priority, item)
        
    def put(self, priority, item):
        # TODO: Implement binary search two increase insert speed
        i = len(self._stack)
        for i in range(len(self._stack) - 1, -1, -1): # Starting at the end
            if self._stack[i][0] < priority:
                i += 1
                break
        self._stack[i:i] = [(priority, item)]
        logger.debug("Put item %s, with priority %s in %dth place of %d", str(item), str(priority), 
                     len(self._stack) - i, len(self._stack))
        
    def pop(self):
        if len(self._stack):
            return self._stack.pop()[1]
        return None
    
    def peek(self):
        if len(self._stack):
            return self._stack[len(self._stack) - 1][1]
        return None
    
    def __iter__(self):
        for i in range(len(self._stack) - 1, -1, -1):
            yield self._stack[i][1]
        
    def __len__(self):
        return len(self._stack)
        