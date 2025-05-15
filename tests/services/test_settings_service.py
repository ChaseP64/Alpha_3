
# Since SettingsService is a singleton and might be imported elsewhere,
# we need to be careful with patching its internal _path for tests.
# The user's test uses _settings_path, let's ensure that's what's intended.
# Reviewing settings_service.py, it uses _path.
# The test should patch SettingsService._path.

def test_last_scale_roundtrip(tmp_path, monkeypatch):
    """Test that setting and getting last_scale works correctly."""
    from digcalc_project.src.services.settings_service import SettingsService

    # Create a unique settings path for this test
    test_settings_file = tmp_path / "test_settings.json"

    # Ensure SettingsService uses this unique path for this test instance
    # The Singleton nature means we need to be careful.
    # If SettingsService() was already called, its _path is set.
    # For a clean test, we might need to reset the singleton or ensure
    # it's instantiated *after* the patch.
    # The monkeypatch on the class attribute should affect subsequent instantiations.

    monkeypatch.setattr(SettingsService, "_path", test_settings_file)

    # Force re-initialization if it's a true singleton that caches instance
    # This depends on the Singleton implementation. If it returns the same instance,
    # and that instance has already initialized its _data based on the original _path,
    # patching _path alone might not be enough without re-triggering __init__ or _load.
    # For now, let's assume the monkeypatch is sufficient before first get/set in test.
    # A more robust way might involve clearing the singleton instance if possible.

    # Resetting the _initialized flag to force re-init if the singleton pattern allows
    if hasattr(SettingsService, "_instance") and SettingsService._instance is not None:
        SettingsService._instance._initialized = False # type: ignore[attr-defined]
        # del SettingsService._instance # This would be more aggressive
        # SettingsService._instance = None # Common way to reset singleton for tests

    svc = SettingsService() # This should now pick up the patched _path

    # Perform the test
    svc.set_last_scale("m", 5.0)
    retrieved_units, retrieved_val = svc.last_scale()

    assert retrieved_units == "m"
    assert retrieved_val == 5.0

    # Verify it's saved and reloaded correctly
    # Create a new instance (should be the same due to singleton) or re-initialize
    if hasattr(SettingsService, "_instance") and SettingsService._instance is not None:
         SettingsService._instance._initialized = False # type: ignore[attr-defined]

    svc_new = SettingsService()
    reloaded_units, reloaded_val = svc_new.last_scale()

    assert reloaded_units == "m"
    assert reloaded_val == 5.0
