
## MAVERICK
### Probe performance data

Values based on 47k measurement resistor.
![Sensor performance chart](MAVERICK_resolution.png)

Property | Symbol | Value
-------- | -------- | --------
Resistance at 0°C | R<sub>25</sub> | 3903.35k
Resistance at 25°C | R<sub>25</sub> | 1001.96k
Resistance at 85°C | R<sub>25</sub> | 73.65k
Beta 25°C to 85°C | B<sub>25/85</sub>| 4646K
Minimum measurable temperature | | 322.6°C
Minimum high-res temperature | | 168.1°C
Highest resolution || 2.72e-02°C/step at 90.3°C
Maximum high-res temperature | | 28.0°C
Maximum measurable temperature | | -14.7°C

### Probe curve data
![Probe fit chart](MAVERICK_curve.png)

Property | Symbol | Value
-------- | -------- | --------
Resistance near 25°C | R<sub>25</sub><sup>1</sup> | 1004.00k
Steinhart-Hart coefficient | a | 3.3561580e-03 ± 1.3829075e-07
Steinhart-Hart coefficient | b | 2.2237925e-04 ± 8.6242782e-08
Steinhart-Hart coefficient | c | 2.6520160e-06 ± 1.3251291e-08

<sup>1</sup>: The deviation between this R<sub>25</sub> and the R<sub>25</sub> shown above is not relevant, this R<sub>25</sub> is taken from the original data point which is closest to 25°C. The value taken as a factor into the calculation of the final value and serves only a scaling purpose to the Steinhart-Hart coefficients.
