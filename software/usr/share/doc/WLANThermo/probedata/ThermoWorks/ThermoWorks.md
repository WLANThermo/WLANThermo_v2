
## ThermoWorks
### Probe performance data

Values based on 47k measurement resistor.
![Sensor performance chart](ThermoWorks_resolution.png)

Property | Symbol | Value
-------- | -------- | --------
Resistance at 0°C | R<sub>25</sub> | 325.18k
Resistance at 25°C | R<sub>25</sub> | 97.33k
Resistance at 85°C | R<sub>25</sub> | 9.94k
Beta 25°C to 85°C | B<sub>25/85</sub>| 4060K
Minimum measurable temperature | | 248.1°C
Minimum high-res temperature | | -21.1°C
Highest resolution || 2.36e-02°C/step at 35.5°C
Maximum high-res temperature | | 108.5°C
Maximum measurable temperature | | -53.8°C

### Probe curve data
![Probe fit chart](ThermoWorks_curve.png)

Property | Symbol | Value
-------- | -------- | --------
Resistance near 25°C | R<sub>25</sub><sup>1</sup> | 97.31k
Steinhart-Hart coefficient | a | 3.3556417e-03 ± 2.2856218e-07
Steinhart-Hart coefficient | b | 2.5191450e-04 ± 1.6501235e-07
Steinhart-Hart coefficient | c | 2.3606960e-06 ± 2.9487291e-08

<sup>1</sup>: The deviation between this R<sub>25</sub> and the R<sub>25</sub> shown above is not relevant, this R<sub>25</sub> is taken from the original data point which is closest to 25°C. The value taken as a factor into the calculation of the final value and serves only a scaling purpose to the Steinhart-Hart coefficients.
