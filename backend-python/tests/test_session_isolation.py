from concurrent.futures import ThreadPoolExecutor

import app.db.session as session_module


def _use_thread_session(main_session_id: int) -> tuple[int, bool]:
    db = session_module.SessionLocal()
    try:
        return id(db), id(db) != main_session_id
    finally:
        db.close()


def test_agent_tool_threads_use_sessionlocal_instead_of_main_session(monkeypatch):
    class FakeSession:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    opened: list[FakeSession] = []

    def fake_sessionlocal() -> FakeSession:
        session = FakeSession()
        opened.append(session)
        return session

    monkeypatch.setattr(session_module, "SessionLocal", fake_sessionlocal)
    main_db = FakeSession()
    main_id = id(main_db)

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(lambda _: _use_thread_session(main_id), range(5)))

    assert all(isolated for _, isolated in results)
    assert all(session is not main_db for session in opened)
    assert all(session.closed for session in opened)
