'''
Created on Aug 7, 2013

@author: Vincent Ketelaars

Generate keys. Output:

generated: Fri Apr 19 17:07:32 2013
curve: high <<< NID_sect571r1 >>>
len: 571 bits ~ 144 bytes signature
pub: 170 3081a7301006072a8648ce3d020106052b8104002703819200040792e72441554e5d5448043bcf516c18d93125cf299244f85fa3bc2c89cdca3029b2f8d832573d337babae5f64ff49dbf70ceca5a0a15e1b13a685c50c4bf285252667e3470b82f90318ac8ee2ad2d09ddabdc140ca879b938921831f0089511321e456b67c3b545ca834f67259e4cf7eff02fbd797c03a2df6db5b945ff3589227d686d6bf593b1372776ece283ab0d
pub-sha1 4fe1172862c649485c25b3d446337a35f389a2a2
-----BEGIN PUBLIC KEY-----
MIGnMBAGByqGSM49AgEGBSuBBAAnA4GSAAQHkuckQVVOXVRIBDvPUWwY2TElzymS
RPhfo7wsic3KMCmy+NgyVz0ze6uuX2T/Sdv3DOyloKFeGxOmhcUMS/KFJSZn40cL
gvkDGKyO4q0tCd2r3BQMqHm5OJIYMfAIlREyHkVrZ8O1RcqDT2clnkz37/AvvXl8
A6LfbbW5Rf81iSJ9aG1r9ZOxNyd27OKDqw0=
-----END PUBLIC KEY-----

'''

import argparse

import dispersy.crypto as Crypto


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generates a new public / private key pair.')
    parser.add_argument("-s", "--security", metavar="SECURITY", default="medium", help='Levels of security: very-low, low, medium, high. Default=medium')
    args = parser.parse_args()
    
    print Crypto.main()
    
    