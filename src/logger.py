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
    from src.definitions import UAV_REPOSITORY_HOME
    uav_logger = None
    try:
        sys.path.index(UAV_REPOSITORY_HOME, 0)
        from Common.API import get_log
        uav_logger = get_log(name)
    except:
        pass    
#     logger.addHandler(logging.StreamHandler(sys.stderr))
#     logger.setLevel(logging.DEBUG)
    return uav_logger