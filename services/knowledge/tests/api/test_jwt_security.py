from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from tests.helpers import clear_modules, configure_runtime_env


def test_jwt_replacement_preserves_signed_tokens_and_rejects_invalid_tokens(monkeypatch, tmp_path):
    configure_runtime_env(monkeypatch, tmp_path)
    clear_modules()
    from app.api.v1 import deps
    from app.config import settings

    monkeypatch.setattr(settings.security, 'SECRET_KEY', 'synthetic-test-signing-key-with-at-least-32-bytes')
    monkeypatch.setattr(settings.security, 'ALGORITHM', 'HS256')
    user = SimpleNamespace(id=17, is_active=True)
    monkeypatch.setattr(deps, 'User', SimpleNamespace(id=17))
    queries = []

    def query(*args):
        queries.append(args)
        return SimpleNamespace(filter=lambda *args: SimpleNamespace(first=lambda: user))

    db = SimpleNamespace(query=query)
    token = deps.jwt.encode({'user_id': 17}, settings.security.SECRET_KEY, algorithm='HS256')
    assert deps._authenticate_user(db, token) is user
    assert len(queries) == 1
    for bad in (
        deps.jwt.encode({'user_id': 17}, 'another-synthetic-key-with-at-least-32-bytes', algorithm='HS256'),
        deps.jwt.encode({'user_id': 17, 'exp': 0}, settings.security.SECRET_KEY, algorithm='HS256'),
        deps.jwt.encode({'user_id': 17}, settings.security.SECRET_KEY, algorithm='HS384'),
        deps.jwt.encode({'user_id': 17}, key='', algorithm='none'),
        'not.a.token',
    ):
        with pytest.raises(HTTPException) as failure:
            deps._authenticate_user(db, bad)
        assert failure.value.status_code == 401
        assert deps._authenticate_user(db, bad, return_none_on_invalid=True) is None
    assert len(queries) == 1
