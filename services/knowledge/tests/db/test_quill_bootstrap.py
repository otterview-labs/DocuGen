def test_knowledge_bootstrap_in_clean_database(tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path

    env = os.environ | {
        "DB_DATABASE_TYPE": "sqlite", "SQLITE_DATABASE": str(tmp_path / "engine.db"),
        "JETLINKS_KNOWLEDGE_ENV": str(tmp_path / "no-env"), "VECTOR_DB_TYPE": "faiss",
    }
    subprocess.run([sys.executable, "-c",
        "from app.db.init_database import init_database; "
        "init_database(create_tables=True, run_migrations=False, initialize_seed_data=False)"],
        cwd=Path(__file__).resolve().parents[2], env=env, check=True,
        capture_output=True, text=True)
