import agentlens


def test_import_exposes_version():
    assert agentlens.__version__ == "0.1.0"


def test_init_is_a_noop():
    result = agentlens.init(api_key="al_test", project="test", endpoint="http://localhost:8000")
    assert result is None


def test_init_accepts_keyword_options():
    assert agentlens.init(flush_interval=1.0, batch_size=10, disabled=True) is None
