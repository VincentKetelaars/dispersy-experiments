'''
Created on Nov 28, 2013

@author: Vincent Ketelaars
'''
import sys

import dispersy.logger as dlogger


def get_logger(name):
    logger = dlogger.get_logger(name)
    return logger

def get_uav_logger(name):
    uav_logger = None
    try:
        from Common.API import get_log
        uav_logger = get_log(name)
    except:
        pass    
#     logger.addHandler(logging.StreamHandler(sys.stderr))
#     logger.setLevel(logging.DEBUG)
    return UAVLoggerWrapper(uav_logger)

class UAVLoggerWrapper(object):
    
    def __init__(self, logger):
        self.logger = logger
        
    def debug(self, *args):
        if self.logger is not None:
            self.logger.debug(*args)
            
    def info(self, *args):
        if self.logger is not None:
            self.logger.info(*args)
        
    def warning(self, *args):
        if self.logger is not None:
            self.logger.warning(*args)
        
    def error(self, *args):
        if self.logger is not None:
            self.logger.error(*args)