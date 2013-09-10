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
    classdocs
    '''

    def i2ithread_readlinecallback(self, ic, cmd):
        words = cmd.split()
        if words[0] == "INFO" or words[0] == "MOREINFO":
            roothash = binascii.unhexlify(words[1])
            try:
                d = self.roothash2dl[roothash]
                d.set_def(SwiftDef(roothash=roothash))
            except:
                logger.error("Could not get FakeSessionSwiftDownloadImpl, INFO might be wrongly attributed")
        return SwiftProcess.i2ithread_readlinecallback(self, ic, cmd)