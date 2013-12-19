'''
Created on Dec 19, 2013

@author: Vincent Ketelaars
'''

from threading import enumerate
import sys
from traceback import extract_stack

class LoggerWrapper():
    
    def __init__(self, logger=None):
        self.logger = logger
        
    def debug(self, *args):
        if self.logger is not None:
            self.logger.debug(*args)
        else:
            if (len(args) > 1):
                print args[0] % args[1:]
            else:
                print args[0]

def print_thread_traces(logger=None):
    printer = LoggerWrapper(logger)
    printer.debug(enumerate())
    code = []
    for threadId, stack in sys._current_frames().items():
        code.append("\n# ThreadID: %s" % threadId)
        for filename, lineno, name, line in extract_stack(stack):
            code.append('File: "%s", line %d, in %s' % (filename, lineno, name))
            if line:
                code.append("  %s" % (line.strip()))

    for line in code:
        printer.debug(line)
        
if __name__ == "__main__":
    print_thread_traces()