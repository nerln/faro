"""faro: one board for everything running in the background on this Mac.

rada counts memory. plancia counts work. Neither counts processes, and the
processes are what quietly take the machine away: a preview server from a
session that closed at three in the morning, a scheduled task nobody remembers
enabling, a launchd job that has been failing since a rename.

faro only looks. It starts nothing, keeps no daemon of its own, and writes
only when told to stop something.
"""

__version__ = "0.1.0"
