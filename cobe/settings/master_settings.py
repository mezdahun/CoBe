import os

master_pass = os.environ.get("MASTER_PASS")

if master_pass is not None:
    master_pass = str(master_pass).strip()