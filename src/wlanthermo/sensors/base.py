"""Gemeinsame Schnittstelle aller Temperaturfühler."""
from abc import ABC, abstractmethod
from typing import Optional


class TemperatureSensor(ABC):
    """Ein Temperaturfühler, der die Temperatur eines Messkanals liefert."""

    #: Bezeichnung, z.B. der Fühlertyp aus sensor.conf
    name = ''

    @abstractmethod
    def read(self) -> Optional[float]:
        """Aktuelle Temperatur in °C, None ohne gültigen Messwert."""

    def __repr__(self):
        return '<{} {}>'.format(type(self).__name__, self.name)
