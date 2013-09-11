'''
Created on Sep 10, 2013

@author: Vincent Ketelaars
'''

import binascii

from Tribler.Core.Swift.SwiftDef import SwiftDef
from Tribler.Core.Swift.SwiftProcess import SwiftProcess

import logging
logger = logging.getLogger()

class MySwiftProcess(SwiftProcess):
    '''
    Probably not necessary!
    '''

    def i2ithread_readlinecallback(self, ic, cmd):
        return SwiftProcess.i2ithread_readlinecallback(self, ic, cmd)