"""Temperaturfühler.

Alle Fühler erben von TemperatureSensor und liefern mit read() die Temperatur
in °C oder None.

    base          TemperatureSensor
    adc           AD-Wandler MCP3208, Abtastung und Filter
    resistive     NtcProbe, PtProbe (Widerstandsfühler am AD-Wandler)
    thermocouple  Ad595Thermocouple (am AD-Wandler), Max31855Thermocouple
    maverick      MaverickProbe (Funkthermometer), receiver: Dienst wlanthermo-maverick
    catalog       Fühlertypen aus sensor.conf
"""
from .base import TemperatureSensor

__all__ = ['TemperatureSensor']
