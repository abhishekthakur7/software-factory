#!/usr/bin/env python3
"""A recipe fixture that sleeps well past any timeout a test declares."""
import sys
import time

time.sleep(5)
sys.exit(0)
