"""
This file is merely to set some parameters for the testcases
"""

import os

DIRECTORY = os.getenv("HOME") + "/Downloads"

# Minimum of 2 files
FILES = list([os.getenv("HOME") + "/Desktop/test_large/tutorial.pdf", os.getenv("HOME") + "/Desktop/test_large/tests/ds/test1"])

DISPERSY_WORKDIR = os.getenv("HOME") + u"/Downloads"

SMALL_TASK_TIMEOUT = 0.01
TIMEOUT_TESTS = 10 # Seconds