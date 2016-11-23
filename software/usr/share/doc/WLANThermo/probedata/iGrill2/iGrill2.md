
## iGrill2
### Probe performance data

Values based on 47k measurement resistor.
![Sensor performance chart](iGrill2_resolution.png)

Property | Symbol | Value
-------- | -------- | --------
Resistance at 0°C | R<sub>0</sub> | 329.32k
Resistance at 25°C | R<sub>25</sub> | 99.40k
Resistance at 85°C | R<sub>85</sub> | 10.18k
Beta 25°C to 85°C | B<sub>25/85</sub>| 4056K
Minimum measurable temperature | | -57.2°C
Minimum high-res temperature | | -20.8°C
Highest resolution || 2.38e-02°C/step at 36.2°C
Maximum high-res temperature | | 109.3°C
Maximum measurable temperature | | 256.9°C

### Probe curve data
![Probe fit chart](iGrill2_curve.png)

Property | Symbol | Value
-------- | -------- | --------
Resistance near 25°C | R<sub>25</sub><sup>1</sup> | 99.61k
Steinhart-Hart coefficient | a | 3.3562424e-03 ± 2.7935477e-07
Steinhart-Hart coefficient | b | 2.5319218e-04 ± 2.0112216e-07
Steinhart-Hart coefficient | c | 2.7988397e-06 ± 3.5746179e-08

<sup>1</sup>: The deviation between this R<sub>25</sub> and the R<sub>25</sub> shown above is not relevant, this R<sub>25</sub> is taken from the original data point which is closest to 25°C. The value taken as a factor into the calculation of the final value and serves only a scaling purpose to the Steinhart-Hart coefficients.
