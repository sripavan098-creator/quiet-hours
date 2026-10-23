"""Clear deployment settings before the server module reads them.

The server reads QH_ENV, RING_WEBHOOK_SECRET and friends when it is imported.
A developer's shell may export them, which would change what the tests see.
Import this module before importing server in any test file.
"""
import os

for _key in ("QH_ENV", "RING_WEBHOOK_SECRET", "QH_CAREGIVER_TOKEN", "QH_DB_PATH", "RING_DEVICE_ZONES"):
    os.environ.pop(_key, None)
