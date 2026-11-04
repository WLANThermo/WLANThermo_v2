"""Einstellungen eines Pitmasters aus WLANThermo.conf, Abschnitt [Pitmaster] bzw. [Pitmaster2]."""
from dataclasses import dataclass, field
from typing import List, Tuple


def section_suffix(instance):
    """'' für den ersten Pitmaster, '2' für den zweiten (Abschnitte, Dateien, Logger)."""
    return str(instance + 1) if instance > 0 else ''


@dataclass
class ActuatorSettings:
    """Grenzen und Optionen der Stellglieder."""
    pwm_min: float          # % bei Stellwert 0
    pwm_max: float          # % bei Stellwert 100
    inverted: bool
    servo_min: float        # Pulsbreite in µs
    servo_max: float
    servo_inverted: bool
    servo_deadband: float   # % des Servobereichs
    startup_min: float      # Anlaufhilfe: Mindestwert in %
    startup_threshold: float
    startup_time: float     # s
    damper_offset: float
    damper_pitch: float


@dataclass
class PidSettings:
    kp: float
    ki: float
    kd: float
    # Parameter unterhalb von switch_a % der Solltemperatur (Anheizen)
    kp_a: float
    ki_a: float
    kd_a: float
    switch_a: float
    iterm_min: float
    iterm_max: float


@dataclass
class LidSettings:
    """Deckelerkennung: Temperatursturz unter falling_border % gilt als offener Deckel."""
    enabled: bool
    pause: float            # s ohne Regelung, höchstens
    falling_border: float
    rising_border: float


@dataclass
class PitmasterSettings:
    on: bool
    pit_type: str           # fan, fan_pwm, servo, io, io_pwm, damper
    controller_type: str    # 'PID' oder 'False' (Wertekurve)
    setpoint: float
    channel: int
    pause: float            # Zykluszeit in s
    manual: float           # > 0: fester Stellwert in %
    curve: List[Tuple[float, float]] = field(default_factory=list)   # (Abweichung, Stellwert)
    ratelimit_rise: float = 0   # s für 0 -> 100 %, 0 = aus
    ratelimit_fall: float = 0
    actuator: ActuatorSettings = None
    pid: PidSettings = None
    lid: LidSettings = None


def parse_curve(text, logger):
    """'-15!100|-10!75|...' -> [(-15.0, 100.0), (-10.0, 75.0), ...]"""
    steps = []
    for step in text.split('|'):
        fields = step.split('!')
        try:
            steps.append((float(fields[0]), float(fields[1])))
        except ValueError:
            logger.error('Illegal step in configuration: {}'.format(step))
    return steps


class _Section:
    """Zugriff auf einen Abschnitt; fehlende Werte ohne Vorgabe lösen NoOptionError aus."""

    def __init__(self, config, name):
        self.config = config
        self.name = name

    def get(self, option):
        return self.config.get(self.name, option)

    def getfloat(self, option, default=None):
        if default is None:
            return self.config.getfloat(self.name, option)
        return self.config.getfloat(self.name, option, fallback=default)

    def getboolean(self, option):
        return self.config.getboolean(self.name, option)


def parse_pitmaster_settings(config, instance, logger):
    section = _Section(config, 'Pitmaster' + section_suffix(instance))
    get, getfloat, getboolean = section.get, section.getfloat, section.getboolean
    return PitmasterSettings(
        on=config.getboolean('ToDo', 'pit' + section_suffix(instance) + '_on'),
        pit_type=get('pit_type'),
        controller_type=get('pit_controller_type'),
        setpoint=getfloat('pit_set'),
        channel=config.getint(section.name, 'pit_ch'),
        pause=getfloat('pit_pause'),
        manual=getfloat('pit_man'),
        curve=parse_curve(get('pit_curve'), logger),
        ratelimit_rise=getfloat('pit_ratelimit_rise'),
        ratelimit_fall=getfloat('pit_ratelimit_fall'),
        actuator=ActuatorSettings(
            pwm_min=getfloat('pit_pwm_min'),
            pwm_max=getfloat('pit_pwm_max'),
            inverted=getboolean('pit_inverted'),
            servo_min=getfloat('pit_servo_min'),
            servo_max=getfloat('pit_servo_max'),
            servo_inverted=getboolean('pit_servo_inverted'),
            servo_deadband=getfloat('pit_servo_deadband'),
            startup_min=getfloat('pit_startup_min', 25.0),
            startup_threshold=getfloat('pit_startup_threshold', 0.0),
            startup_time=getfloat('pit_startup_time', 0.5),
            damper_offset=getfloat('pit_damper_offset'),
            damper_pitch=getfloat('pit_damper_pitch'),
        ),
        pid=PidSettings(
            kp=getfloat('pit_kp'), ki=getfloat('pit_ki'), kd=getfloat('pit_kd'),
            kp_a=getfloat('pit_kp_a'), ki_a=getfloat('pit_ki_a'), kd_a=getfloat('pit_kd_a'),
            switch_a=getfloat('pit_switch_a'),
            iterm_min=getfloat('pit_iterm_min'), iterm_max=getfloat('pit_iterm_max'),
        ),
        lid=LidSettings(
            enabled=getboolean('pit_open_lid_detection'),
            pause=getfloat('pit_open_lid_pause'),
            falling_border=getfloat('pit_open_lid_falling_border'),
            rising_border=getfloat('pit_open_lid_rising_border'),
        ),
    )
