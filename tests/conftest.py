import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Make ryotenkai.py importable from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def mock_client():
    """A MagicMock MsfRpcClient. Tests set .jobs.list, .sessions.list, etc."""
    client = MagicMock()
    client.jobs.list = {}
    client.sessions.list = {}
    return client
