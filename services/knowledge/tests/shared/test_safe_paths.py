from pathlib import Path

import pytest

from tests.helpers import clear_modules, configure_runtime_env


def test_containment_rejects_traversal_absolute_sibling_and_symlinks(tmp_path):
    from app.shared.utils.safe_paths import contained_path

    root = tmp_path / 'uploads'
    root.mkdir()
    nested = root / 'temp'
    nested.mkdir()
    good = nested / 'clip.mp4'
    good.write_bytes(b'synthetic')
    outside = tmp_path / 'uploads-private'
    outside.mkdir()
    secret = outside / 'private.txt'
    secret.write_text('synthetic private data')
    (root / 'link').symlink_to(outside, target_is_directory=True)
    assert contained_path(root, 'temp/clip.mp4') == good
    for value in ('../uploads-private/private.txt', str(secret), 'link/private.txt', '.'):
        with pytest.raises(ValueError):
            contained_path(root, value)


@pytest.mark.parametrize('value', ['../secret', 'temp/../../secret', '/etc/passwd', 'a\\..\\secret', 'a/./b', 'a//b', '\x00'])
def test_relative_names_reject_unsafe_components(value):
    from app.shared.utils.safe_paths import relative_file_name

    with pytest.raises(ValueError):
        relative_file_name(value)


def test_media_processing_only_accepts_storage_files(monkeypatch, tmp_path):
    configure_runtime_env(monkeypatch, tmp_path)
    clear_modules()
    from app.config import settings
    from app.shared.audio_processor import media_processor
    from app.shared.utils.file_detector import FileTypeDetector

    upload = Path(settings.storage.STATIC_DIR) / 'uploads' / '-clip.mp4'
    upload.write_bytes(b'synthetic')
    outside = tmp_path / 'private.mp4'
    outside.write_bytes(b'private')
    (upload.parent / 'link.mp4').symlink_to(outside)
    processor = media_processor.MediaProcessor(check_ffmpeg=False)
    monkeypatch.setattr(media_processor, 'IMAGEIO_FFMPEG_AVAILABLE', False)
    monkeypatch.setattr(media_processor, 'FFMPEG_PYTHON_AVAILABLE', False)
    calls = []

    def run(cmd, **kwargs):
        from types import SimpleNamespace
        calls.append(cmd)
        return SimpleNamespace(stdout='{"streams": [], "format": {}}')

    monkeypatch.setattr(media_processor.subprocess, 'run', run)
    processor.get_media_info(str(upload))
    assert calls[0][-2:] == ['-i', str(upload)]
    for path in (outside, upload.parent / 'link.mp4'):
        with pytest.raises(ValueError):
            processor.get_media_info(str(path))
        assert FileTypeDetector().validate_file(str(path))['success'] is False
    assert len(calls) == 1
    assert processor._safe_parse_fps('__import__("os").system("false")') == 0
    assert processor._safe_parse_fps('30000/1001') == pytest.approx(29.97003)
