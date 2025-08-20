"""Tests for the PropertiesDock UI component."""

import pytest
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox

from digcalc_project.src.services.settings_service import SettingsService

# Widget being tested
from digcalc_project.src.ui.properties_dock import PropertiesDock
from digcalc_project.src.utils.singleton import Singleton


@pytest.fixture(autouse=True)
def settings_for_test(monkeypatch, temporary_settings):
    """Fixture to ensure all tests in this file use a temporary settings file."""
    # Force the singleton to use our temporary path for the duration of the tests
    monkeypatch.setattr(SettingsService, "_path", temporary_settings)

    # Clear any existing singleton instance to ensure the new path is used on next creation
    Singleton.clear_instances()

    # Provide a fresh instance with defaults for each test
    settings = SettingsService()
    settings._settings = settings._DEFAULTS.copy()
    settings.save()

    yield settings

    # Clean up after tests
    Singleton.clear_instances()


@pytest.fixture
def dock(qtbot) -> PropertiesDock:
    """Create an instance of PropertiesDock for testing."""
    widget = PropertiesDock()
    qtbot.addWidget(widget)  # Manage widget lifetime
    # Ensure the tracing tab widgets are created and accessible
    assert hasattr(widget, "_spline_sampling_spin")
    assert hasattr(widget, "_elev_mode_combo")
    return widget


def test_initial_tracing_values(dock: PropertiesDock, settings_for_test: SettingsService):
    """Test that tracing widgets load initial values from SettingsService."""
    initial_sampling = settings_for_test.smooth_sampling_ft()
    initial_mode = settings_for_test.tracing_elev_mode()

    sampling_spin: QDoubleSpinBox = dock._spline_sampling_spin
    mode_combo: QComboBox = dock._elev_mode_combo

    assert sampling_spin.value() == pytest.approx(initial_sampling)
    assert mode_combo.currentData() == initial_mode


def test_sampling_spinbox_updates_setting(
    qtbot, dock: PropertiesDock, settings_for_test: SettingsService
):
    """Test changing the sampling spinbox updates the SettingsService."""
    sampling_spin: QDoubleSpinBox = dock._spline_sampling_spin
    initial_value = sampling_spin.value()
    new_value = initial_value + 0.5
    if new_value > sampling_spin.maximum():
        new_value = initial_value - 0.5  # Adjust if already at max

    # Simulate user changing the value using Qt API directly
    sampling_spin.setValue(new_value)
    qtbot.wait(50)

    # Check that the setting was updated
    assert settings_for_test.smooth_sampling_ft() == pytest.approx(new_value)


def test_elevation_mode_combobox_updates_setting(
    qtbot, dock: PropertiesDock, settings_for_test: SettingsService
):
    """Test changing the elevation mode combobox updates the SettingsService."""
    mode_combo: QComboBox = dock._elev_mode_combo
    initial_index = mode_combo.currentIndex()
    new_index = (initial_index + 1) % mode_combo.count()  # Cycle to next index

    # Simulate user changing the value
    mode_combo.setCurrentIndex(new_index)
    qtbot.wait(50)

    # Check that the setting was updated
    new_mode = mode_combo.itemData(new_index)
    assert settings_for_test.tracing_elev_mode() == new_mode


def test_settings_changed_signal_emitted(qtbot, dock: PropertiesDock):
    """Test that the settingsChanged signal is emitted when widgets change."""
    sampling_spin: QDoubleSpinBox = dock._spline_sampling_spin
    mode_combo: QComboBox = dock._elev_mode_combo

    with qtbot.waitSignal(dock.settingsChanged, timeout=1000) as sampling_blocker:
        sampling_spin.setValue(sampling_spin.value() + 0.1)

    # Assert the signal was received
    assert sampling_blocker.signal_triggered

    with qtbot.waitSignal(dock.settingsChanged, timeout=1000) as mode_blocker:
        mode_combo.setCurrentIndex((mode_combo.currentIndex() + 1) % mode_combo.count())
        qtbot.wait(10)

    # Assert the signal was received
    assert mode_blocker.signal_triggered


def test_load_persisted_values_on_recreation(qtbot, settings_for_test: SettingsService):
    # Set non-default values and save
    test_sampling = 5.5
    test_mode = "interpolate"
    settings_for_test.set_smooth_sampling_ft(test_sampling)
    settings_for_test.set_tracing_elev_mode(test_mode)
    settings_for_test.save()

    # Re-create the dock - it should now load the persisted values
    dock = PropertiesDock()
    qtbot.addWidget(dock)

    sampling_spin: QDoubleSpinBox = dock._spline_sampling_spin
    mode_combo: QComboBox = dock._elev_mode_combo

    assert sampling_spin.value() == pytest.approx(test_sampling)
    assert mode_combo.currentData() == test_mode
