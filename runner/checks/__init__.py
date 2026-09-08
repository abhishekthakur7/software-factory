"""Pure check functions over already-collected evidence: no filesystem or network access, no agent.

Each module here (`exclusion` first) computes a check's result or decision
from data already in hand -- ticket fields, loaded configuration, a diff's
path list -- and returns it; writing that result to the database, and
applying whatever transition it implies, stays the caller's job.
"""
