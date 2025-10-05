import os

import pytest

from app.core.utils import FileUtils
from app.media.video import VideoGenerator


@pytest.mark.unit
def test_utils_get_temp_file_creates_unique_files():
    path_one = FileUtils.get_temp_file(prefix="unit_", suffix=".tmp")
    path_two = FileUtils.get_temp_file(prefix="unit_", suffix=".tmp")

    try:
        assert path_one != path_two
        assert os.path.exists(path_one)
        assert os.path.exists(path_two)
        assert os.path.dirname(path_one).endswith("temp")
        assert os.path.dirname(path_two).endswith("temp")
    finally:
        for path in (path_one, path_two):
            if os.path.exists(path):
                os.remove(path)


@pytest.mark.unit
def test_video_generator_creates_temp_background_file():
    generator = VideoGenerator()
    temp_path = generator._create_simple_background()

    try:
        assert temp_path
        assert os.path.exists(temp_path)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
