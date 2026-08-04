from plane_mcp_gateway.__main__ import main


def test_server_disables_access_log_to_avoid_query_secret_leaks(monkeypatch):
    options: dict[str, object] = {}

    def capture_run(app: str, **kwargs):
        options.update(app=app, **kwargs)

    monkeypatch.setattr("plane_mcp_gateway.__main__.uvicorn.run", capture_run)

    main()

    assert options["access_log"] is False
