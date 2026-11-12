import logging
import math
import time
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

# dronekit es una dependencia opcional de simulación.
# Se importa de forma lazy para que el servidor FastAPI pueda arrancar
# en entornos sin dronekit (producción, CI, tests).
try:
    import collections
    import collections.abc

    # Parche para compatibilidad de dronekit con Python 3.10+
    collections.MutableMapping = collections.abc.MutableMapping

    from dronekit import LocationGlobalRelative, VehicleMode
    from dronekit import connect as dronekit_connect

    _DRONEKIT_AVAILABLE = True
except ImportError:
    _DRONEKIT_AVAILABLE = False
    logger.warning(
        "dronekit no está instalado — los endpoints de control de vuelo "
        "estarán deshabilitados. Instálalo con: pip install dronekit"
    )


def _require_dronekit():
    if not _DRONEKIT_AVAILABLE:
        raise RuntimeError("dronekit no está instalado. Ejecuta: pip install dronekit  (requiere entorno SITL)")


class FlightCancelled(RuntimeError):
    """La navegación se interrumpió antes de emitir el siguiente comando."""


class DroneService:
    def __init__(self, *, poll_interval=0.25, clock=time.monotonic, sleep=time.sleep):
        self.vehicle = None
        self.poll_interval = poll_interval
        self.clock = clock
        self.sleep = sleep

    def ensure_connected(self):
        _require_dronekit()
        if self.vehicle is None:
            raise RuntimeError("Dron no conectado")
        heartbeat = self.vehicle.last_heartbeat
        if heartbeat is None or not math.isfinite(heartbeat) or not 0 <= heartbeat <= 5:
            raise RuntimeError("Telemetría del dron ausente o desactualizada")

    def telemetry(self):
        self.ensure_connected()
        vehicle = self.vehicle
        position = vehicle.location.global_relative_frame

        def finite(value, minimum=-math.inf, maximum=math.inf):
            if value is None or not math.isfinite(value) or not minimum <= value <= maximum:
                return None
            return float(value)

        return {
            "timestamp": datetime.now(UTC),
            "heartbeat_age_seconds": vehicle.last_heartbeat,
            "armed": vehicle.armed,
            "mode": getattr(vehicle.mode, "name", None),
            "latitude": finite(position.lat, -90, 90),
            "longitude": finite(position.lon, -180, 180),
            "relative_altitude_m": finite(position.alt),
            "battery_percent": finite(getattr(vehicle.battery, "level", None), 0, 100),
            "groundspeed_m_s": finite(vehicle.groundspeed, 0),
        }

    def is_grounded(self):
        self.ensure_connected()
        altitude = self.vehicle.location.global_relative_frame.alt
        return not self.vehicle.armed and altitude is not None and math.isfinite(altitude) and abs(altitude) <= 1.0

    def ensure_ready(self):
        if not self.is_grounded():
            raise RuntimeError("El dron debe estar desarmado y en tierra para iniciar una misión")

    def _wait(self, predicate, timeout, description, cancel=None, guided=False):
        deadline = self.clock() + timeout
        while True:
            self.ensure_connected()
            if cancel is not None and cancel.is_set():
                raise FlightCancelled("Cancelación solicitada")
            if guided and self.vehicle.mode.name != "GUIDED":
                raise RuntimeError("El vehículo abandonó el modo GUIDED")
            if predicate():
                return
            if self.clock() >= deadline:
                raise TimeoutError(f"Tiempo agotado: {description}")
            self.sleep(self.poll_interval)

    def connect(self, connection_string: str = "127.0.0.1:14550") -> bool:
        _require_dronekit()
        if self.vehicle:
            self.ensure_connected()
            return True
        try:
            self.vehicle = dronekit_connect(connection_string, wait_ready=True, timeout=30, heartbeat_timeout=15)
            return True
        except Exception:
            logger.exception("No se pudo conectar al dron")
            return False

    def arm_and_takeoff(self, target_altitude: float, cancel=None, timeout=90) -> bool:
        self.ensure_ready()
        if not math.isfinite(target_altitude) or not 2 <= target_altitude <= 200:
            raise ValueError("Altitud fuera de rango (2–200 metros)")
        self._wait(lambda: self.vehicle.is_armable, timeout, "prearmado", cancel)
        self._set_mode("GUIDED")
        self._wait(lambda: self.vehicle.mode.name == "GUIDED", timeout, "modo GUIDED", cancel)
        self.vehicle.armed = True
        self._wait(lambda: self.vehicle.armed, timeout, "armado", cancel, guided=True)
        self.vehicle.simple_takeoff(target_altitude)
        self._wait(
            lambda: (
                self.vehicle.location.global_relative_frame.alt is not None
                and self.vehicle.location.global_relative_frame.alt >= target_altitude * 0.95
            ),
            timeout,
            "despegue",
            cancel,
            guided=True,
        )
        return True

    def goto_waypoint(self, waypoint, cancel=None, timeout=180):
        self.ensure_connected()
        if cancel is not None and cancel.is_set():
            raise FlightCancelled("Cancelación solicitada")
        if not self.vehicle.armed or self.vehicle.mode.name != "GUIDED":
            raise RuntimeError("La navegación requiere un vehículo armado en GUIDED")
        target = LocationGlobalRelative(waypoint.latitud, waypoint.longitud, waypoint.altitud_metros)
        self.vehicle.simple_goto(target)

        def arrived():
            if not self.vehicle.armed:
                raise RuntimeError("El vehículo se desarmó durante la navegación")
            pos = self.vehicle.location.global_relative_frame
            values = (pos.lat, pos.lon, pos.alt)
            if any(value is None or not math.isfinite(value) for value in values):
                return False
            lat1, lat2 = math.radians(pos.lat), math.radians(waypoint.latitud)
            dlat = lat2 - lat1
            dlon = math.radians(waypoint.longitud - pos.lon)
            a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
            distance = 6371000 * 2 * math.asin(math.sqrt(min(1, max(0, a))))
            return distance <= 3 and abs(pos.alt - waypoint.altitud_metros) <= 1

        self._wait(arrived, timeout, "llegada al waypoint", cancel, guided=True)

    def return_to_launch(self) -> bool:
        self.ensure_connected()
        self._set_mode("RTL")
        return True

    def _set_mode(self, name):
        # ArduCopter 3.3 no acepta MAV_CMD_DO_SET_MODE usado por DroneKit actual.
        # SET_MODE usa solo CUSTOM_MODE_ENABLED; no fuerza el bit de armado.
        version = getattr(self.vehicle, "version", None)
        major, minor = getattr(version, "major", None), getattr(version, "minor", None)
        if major == 3 and isinstance(minor, int) and minor <= 3:
            master = self.vehicle._master
            modes = master.mode_mapping()
            if not modes or name not in modes:
                raise RuntimeError("Modo de vuelo no disponible")
            master.mav.set_mode_send(master.target_system, 1, modes[name])
        else:
            self.vehicle.mode = VehicleMode(name)

    def wait_landed(self, timeout=180):
        self._wait(self.is_grounded, timeout, "aterrizaje y desarmado")

    def close(self) -> None:
        if self.vehicle:
            self.vehicle.close()
            self.vehicle = None


# Instancia global del servicio
drone_service = DroneService()
