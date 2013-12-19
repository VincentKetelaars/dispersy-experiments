'''
Created on Aug 7, 2013

@author: Vincent Ketelaars
'''
from os.path import exists
from logging.config import fileConfig

if exists("logger.conf"):
    try:
        fileConfig("logger.conf")
        print "logger.conf configured logging"
    except:
        print "Could not open logger.conf"
else:
    print "logger.conf does not exist"