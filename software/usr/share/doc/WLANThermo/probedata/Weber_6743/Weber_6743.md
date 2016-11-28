
## Weber_6743
### Probe performance data

Values based on 47k measurement resistor.
![Sensor performance chart](Weber_6743_resolution.png)

Property | Symbol | Value
-------- | -------- | --------
Resistance at 0°C | R<sub>0</sub> | 313.00k
Resistance at 25°C | R<sub>25</sub> | 102.25k
Resistance at 85°C | R<sub>85</sub> | 12.18k
Beta 25°C to 85°C | B<sub>25/85</sub>| 3787K
Minimum measurable temperature | | -61.1°C
Minimum high-res temperature | | -21.9°C
Highest resolution || 2.57e-02°C/step at 37.2°C
Maximum high-res temperature | | 113.7°C
Maximum measurable temperature | | 287.6°C

### Probe curve data
![Probe fit chart](Weber_6743_curve.png)

Property | Symbol | Value
-------- | -------- | --------
Resistance near 25°C | R<sub>25</sub><sup>1</sup> | 102.31k
Steinhart-Hart coefficient | a | 3.3558796e-03 ± 1.9622046e-07
Steinhart-Hart coefficient | b | 2.7111149e-04 ± 1.5129540e-07
Steinhart-Hart coefficient | c | 3.1838428e-06 ± 2.8818719e-08

<sup>1</sup>: The deviation between this R<sub>25</sub> and the R<sub>25</sub> shown above is not relevant, this R<sub>25</sub> is taken from the original data point which is closest to 25°C. The value taken as a factor into the calculation of the final value and serves only a scaling purpose to the Steinhart-Hart coefficients.
