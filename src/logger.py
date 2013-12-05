'''
Created on Nov 28, 2013

@author: Vincent Ketelaars
'''
import sys
import logging

import dispersy.logger as dlogger
try:
    sys.path.index("/home/vincent/svn/norut/uav/uav/trunk", 0)
    from Common.API import get_log
except:
    pass

def get_logger(name):
    logger = dlogger.get_logger(name)
    try:
        logger = get_log(name)
    except:
        pass
#     logger.addHandler(logging.StreamHandler(sys.stderr))
#     logger.setLevel(logging.DEBUG)
    return logger