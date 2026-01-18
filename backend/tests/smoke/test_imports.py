def test_basic_import():
    import backend.engine.orchestrator as orchestrator

    assert hasattr(orchestrator, "Orchestrator")
