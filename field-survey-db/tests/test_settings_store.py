"""settings_store — API 키 DPAPI 암호화 저장/로드 라운드트립 + 평문 미노출 검증."""
from core import settings_store as ss


def test_roundtrip_and_no_plaintext_on_disk(tmp_path):
    path = tmp_path / "ai_settings.enc"
    secret = "sk-ant-super-secret-KEY-1234567890"
    encrypted = ss.save(path, "claude", {"claude": secret, "openai": "", "gemini": ""})

    # 로드하면 원래 키가 복원돼야 함
    loaded = ss.load(path)
    assert loaded["provider"] == "claude"
    assert loaded["keys"]["claude"] == secret
    assert loaded["keys"]["openai"] == ""

    # DPAPI 가능 환경이면 디스크 파일에 평문 키가 남지 않아야 함
    on_disk = path.read_text(encoding="utf-8")
    if encrypted:
        assert secret not in on_disk


def test_status_hides_keys(tmp_path):
    path = tmp_path / "s.enc"
    ss.save(path, "openai", {"claude": "", "openai": "sk-openai-xyz", "gemini": ""})
    st = ss.status(path)
    assert st["provider"] == "openai"
    assert st["configured"] == {"claude": False, "openai": True, "gemini": False}
    # status 결과에 실제 키 문자열이 들어있지 않아야 함
    assert "sk-openai-xyz" not in str(st)


def test_missing_file_defaults(tmp_path):
    st = ss.load(tmp_path / "none.enc")
    assert st["provider"] == "claude"
    assert st["keys"] == {"claude": "", "openai": "", "gemini": ""}
