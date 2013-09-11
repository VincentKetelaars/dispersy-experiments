'''
Created on Sep 10, 2013

@author: Vincent Ketelaars
'''
import sys

from Tribler.Core.Swift.SwiftProcess import SwiftProcess

import logging
logger = logging.getLogger()

class MySwiftProcess(SwiftProcess):
    '''
    Probably not necessary!
    '''
    def set_on_swift_restart_callback(self, callback):
        self.swift_restart_callback = callback
    
    def i2ithread_readlinecallback(self, ic, cmd):
#         words = cmd.split()
#         if words[0] == "ERROR":
#             self.connection_lost(self.get_cmdport())
        return SwiftProcess.i2ithread_readlinecallback(self, ic, cmd)
    
    def write(self, msg):
        if self.fastconn is not None:
            SwiftProcess.write(self, msg)
            
    def connection_lost(self, port):
        self.swift_restart_callback()
        
            