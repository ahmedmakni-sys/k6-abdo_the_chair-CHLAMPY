"""Recording helper: reads a trial's answer from the database so the demo bot can respond plausibly.

The server never sends answers to the browser, so this reads the database file directly.
Usage: python oracle.py <db path> <trial id>
"""

import json
import sqlite3
import sys

db = sqlite3.connect(sys.argv[1])
row = db.execute("SELECT item_json FROM trial WHERE id = ?", (int(sys.argv[2]),)).fetchone()
item = json.loads(row[0])
print(json.dumps(item["answer"]))
