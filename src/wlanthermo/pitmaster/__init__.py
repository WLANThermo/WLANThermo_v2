"""Pitmaster: regelt die Garraumtemperatur über ein Stellglied (Lüfter, Servo, Heizung, ...).

    service    Pitmaster (Regelzyklus) und main(), Dienst wlanthermo-pitmaster
    settings   Einstellungen aus [Pitmaster] bzw. [Pitmaster2]
    controller Regler: StepCurveController (Wertekurve), PidController,
               OpenLidDetector (Deckelerkennung), limit_rate()
    actuators  Stellglieder: Fan, FanPwm, Servo, IoPwm, Io, Damper; Output
"""
