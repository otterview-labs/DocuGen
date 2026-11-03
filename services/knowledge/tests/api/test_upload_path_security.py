import sys
from types import SimpleNamespace

import pytest

from tests.helpers import clear_modules, configure_runtime_env, make_stub_module


@pytest.mark.asyncio
async def test_process_url_validates_before_invoking_parser(monkeypatch, tmp_path):
    configure_runtime_env(monkeypatch, tmp_path)
    clear_modules()
    monkeypatch.chdir(tmp_path)
    uploads = tmp_path / 'storage/static/uploads'
    uploads.mkdir(parents=True)
    good = uploads / 'sample.txt'
    good.write_text('synthetic upload')
    private = tmp_path / 'private.txt'
    private.write_text('private sentinel')
    (uploads / 'escape.txt').symlink_to(private)
    calls = []

    async def process(**kwargs):
        calls.append(kwargs)
        return {'success': True, 'content_id': 'synthetic'}

    monkeypatch.setitem(sys.modules, 'app.services.multimodal_upload_service', make_stub_module(
        'app.services.multimodal_upload_service', multimodal_service=SimpleNamespace(), process_multimodal_upload=process,
    ))
    from app.api.v1.rag.endpoints.simple_upload import process_from_url

    for url in ('/uploads/../../../private.txt', '/uploads//etc/passwd', '/uploads/a\\..\\private.txt', '/uploads/escape.txt'):
        result = await process_from_url(url=url, title=None, collection_id='default', parse_options_json=None, db=None)
        assert result['status'] == 400, url
    assert calls == []
    result = await process_from_url(url='/uploads/sample.txt', title=None, collection_id='default', parse_options_json=None, db=None)
    assert result['success'] is True
    assert calls[0]['file_path'] == str(good)
