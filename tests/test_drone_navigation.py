from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.schemas.mission import WaypointBase
from app.services import drone_service as module
from app.services.drone_service import DroneService, FlightCancelled


@pytest.fixture()
def flight(monkeypatch):
    monkeypatch.setattr(module, "_DRONEKIT_AVAILABLE", True)
    monkeypatch.setattr(module, "VehicleMode", lambda name: SimpleNamespace(name=name), raising=False)
    monkeypatch.setattr(
        module,
        "LocationGlobalRelative",
        lambda lat, lon, alt: SimpleNamespace(lat=lat, lon=lon, alt=alt),
        raising=False,
    )
    ticks = iter(range(1000))
    service = DroneService(clock=lambda: next(ticks), sleep=lambda _: None)
    service.vehicle = Mock(
        armed=True,
        last_heartbeat=0,
        location=SimpleNamespace(global_relative_frame=SimpleNamespace(lat=20.0, lon=-100.0, alt=15.0)),
    )
    service.vehicle.mode = SimpleNamespace(name="GUIDED")
    return service


def waypoint(**kwargs):
    return WaypointBase(orden_waypoint=1, latitud=20, longitud=-100, **kwargs)


def test_arrival_checks_position_and_altitude(flight):
    flight.goto_waypoint(waypoint())
    target = flight.vehicle.simple_goto.call_args.args[0]
    assert (target.lat, target.lon, target.alt) == (20, -100, 15)


@pytest.mark.parametrize("coordinate,value", [("lat", 21), ("lon", -101), ("alt", 8)])
def test_does_not_complete_until_target_is_reached(flight, coordinate, value):
    setattr(flight.vehicle.location.global_relative_frame, coordinate, value)
    with pytest.raises(TimeoutError, match="waypoint"):
        flight.goto_waypoint(waypoint(), timeout=2)


def test_cancellation_prevents_next_command(flight):
    cancel = Event()
    cancel.set()
    with pytest.raises(FlightCancelled):
        flight.goto_waypoint(waypoint(), cancel)
    flight.vehicle.simple_goto.assert_not_called()


def test_connection_loss_aborts_navigation(flight):
    flight.vehicle.last_heartbeat = 10
    with pytest.raises(RuntimeError, match="desactualizada"):
        flight.goto_waypoint(waypoint())
    flight.vehicle.simple_goto.assert_not_called()


def test_land_requires_disarmed_and_low_altitude(flight):
    flight.vehicle.armed = False
    with pytest.raises(TimeoutError, match="aterrizaje"):
        flight.wait_landed(timeout=2)
    flight.vehicle.location.global_relative_frame.alt = 0
    flight.wait_landed(timeout=2)


def test_takeoff_times_out_before_arming(flight):
    flight.vehicle.armed = False
    flight.vehicle.location.global_relative_frame.alt = 0
    flight.vehicle.is_armable = False
    with pytest.raises(TimeoutError, match="prearmado"):
        flight.arm_and_takeoff(10, timeout=2)
    assert flight.vehicle.armed is False
    flight.vehicle.simple_takeoff.assert_not_called()


def test_takeoff_and_return(flight):
    flight.vehicle.armed = False
    flight.vehicle.location.global_relative_frame.alt = 0
    flight.vehicle.is_armable = True
    flight.vehicle.simple_takeoff.side_effect = lambda alt: setattr(
        flight.vehicle.location.global_relative_frame, "alt", alt
    )
    assert flight.arm_and_takeoff(12)
    assert flight.vehicle.armed is True
    assert flight.return_to_launch()
    assert flight.vehicle.mode.name == "RTL"


def test_legacy_copter_uses_set_mode_without_arming_bit(flight):
    flight.vehicle.version = SimpleNamespace(major=3, minor=3)
    flight.vehicle._master.target_system = 1
    flight.vehicle._master.mode_mapping.return_value = {"GUIDED": 4, "RTL": 6}
    flight._set_mode("GUIDED")
    flight.vehicle._master.mav.set_mode_send.assert_called_once_with(1, 1, 4)
