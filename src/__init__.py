'''
Created on Aug 7, 2013

@author: Vincent Ketelaars
'''
import sys
from os.path import exists
from logging.config import fileConfig

if exists("logger.conf"):
    try:
        fileConfig("logger.conf")
        print "logger.conf configured logging"
    except IOError:
        print "Could not open logger.conf", sys.exc_info()
else:
    print "logger.conf does not exist"