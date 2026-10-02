from strattester.remote import tailscale
def test_missing_tailscale_is_optional(monkeypatch):
    monkeypatch.setattr(tailscale.shutil,'which',lambda _:None)
    s=tailscale.detect_tailscale()
    assert not s.installed and not s.running
