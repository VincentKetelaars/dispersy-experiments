'''
Created on Aug 7, 2013

@author: Vincent Ketelaars
'''

from dispersy.conversion import BinaryConversion

class MyConversion(BinaryConversion):
    '''
    classdocs
    '''


    def __init__(self, community):
        '''
        Constructor
        '''
        super(MyConversion, self).__init__(community, "\x12")