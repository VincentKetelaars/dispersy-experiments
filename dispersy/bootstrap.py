import os
from socket import gethostbyname

from .candidate import BootstrapCandidate

_trackers = [(u"dispersy1.tribler.org", 6421),
             (u"dispersy2.tribler.org", 6422),
             (u"dispersy3.tribler.org", 6423),
             (u"dispersy4.tribler.org", 6424),
             (u"dispersy5.tribler.org", 6425),
             (u"dispersy6.tribler.org", 6426),
             (u"dispersy7.tribler.org", 6427),
             (u"dispersy8.tribler.org", 6428),

             (u"dispersy1b.tribler.org", 6421),
             (u"dispersy2b.tribler.org", 6422),
             (u"dispersy3b.tribler.org", 6423),
             (u"dispersy4b.tribler.org", 6424),
             (u"dispersy5b.tribler.org", 6425),
             (u"dispersy6b.tribler.org", 6426),
             (u"dispersy7b.tribler.org", 6427),
             (u"dispersy8b.tribler.org", 6428)]

# _trackers = [(u"kayapo.tribler.org", 6431)]


def get_bootstrap_hosts(working_directory):
    """
    Reads WORKING_DIRECTORY/bootstraptribler.txt and returns the hosts therein, otherwise it
    returns _TRACKERS.
    """
    trackers = []
    filename = os.path.join(working_directory, "bootstraptribler.txt")
    try:
        for line in open(filename, "r"):
            line = line.strip()
            if not line.startswith("#"):
                host, port = line.split()
                trackers.append((host.decode("UTF-8"), int(port)))
    except:
        pass

    if trackers:
        return trackers
    else:
        return _trackers


def get_bootstrap_candidates(dispersy):
    """
    Returns a list with all known bootstrap peers.

    Bootstrap peers are retrieved from WORKING_DIRECTORY/bootstraptribler.txt if it exits.
    Otherwise it is created using the trackers defined in _TRACKERS.

    Each bootstrap peer gives either None or a Candidate.  None values can be caused by
    malfunctioning DNS.
    """
    def get_candidate(host, port):
        try:
            return BootstrapCandidate((gethostbyname(host), port), False)
        except:
            return None

    return [get_candidate(host, port) for host, port in get_bootstrap_hosts(dispersy.working_directory)]
