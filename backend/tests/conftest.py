import os

# The in-app scheduler loop must never touch real data while tests run.
os.environ.setdefault("FJG_NO_SCHEDULER", "1")
