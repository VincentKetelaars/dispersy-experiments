'''
Created on Nov 28, 2013

@author: Vincent Ketelaars
'''
import sys
import logging

import dispersy.logger as dlogger
from Common.API import get_log

def get_logger(name):
#     logger = dlogger.get_logger(name)
    logger = get_log(name)
#     logger.addHandler(logging.StreamHandler(sys.stderr))
#     logger.setLevel(logging.DEBUG)
    return logger