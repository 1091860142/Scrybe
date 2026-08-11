"""配置模块单元测试。"""
from app.config import Config, config_path, load_config, save_config


def test_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    cfg = Config(provider="openai_compat", openai_api_key="sk-test", language="zh")
    save_config(cfg)
    loaded = load_config()
    assert loaded.provider == "openai_compat"
    assert loaded.openai_api_key == "sk-test"


def test_defaults_when_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert load_config().provider == "dashscope"
    assert load_config().language == "zh"


def test_corrupt_returns_default(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{bad json", encoding="utf-8")
    assert load_config().provider == "dashscope"
