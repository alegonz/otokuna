import os

import pytest


@pytest.fixture
def set_environ():
    os.environ["OUTPUT_BUCKET"] = "somebucket"
    yield
    os.environ.pop("OUTPUT_BUCKET")
