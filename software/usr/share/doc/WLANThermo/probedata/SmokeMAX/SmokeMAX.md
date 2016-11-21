
## SmokeMAX
### Probe performance data

Values based on 47k measurement resistor.
![Sensor performance chart](SmokeMAX_resolution.png)

Property | Symbol | Value
-------- | -------- | --------
Resistance at 0°C | R<sub>25</sub> | 327.14k
Resistance at 25°C | R<sub>25</sub> | 99.45k
Resistance at 85°C | R<sub>25</sub> | 10.40k
Beta 25°C to 85°C | B<sub>25/85</sub>| 4018K
Minimum measurable temperature | | -57.4°C
Minimum high-res temperature | | -21.0°C
Highest resolution || 2.40e-02°C/step at 36.1°C
Maximum high-res temperature | | 109.8°C
Maximum measurable temperature | | 262.3°C

### Probe curve data
![Probe fit chart](SmokeMAX_curve.png)

Property | Symbol | Value
-------- | -------- | --------
Resistance near 25°C | R<sub>25</sub><sup>1</sup> | 99.64k
Steinhart-Hart coefficient | a | 3.3561946e-03 ± 2.9559938e-07
Steinhart-Hart coefficient | b | 2.5500050e-04 ± 2.1532017e-07
Steinhart-Hart coefficient | c | 2.5976258e-06 ± 3.8763580e-08

<sup>1</sup>: The deviation between this R<sub>25</sub> and the R<sub>25</sub> shown above is not relevant, this R<sub>25</sub> is taken from the original data point which is closest to 25°C. The value taken as a factor into the calculation of the final value and serves only a scaling purpose to the Steinhart-Hart coefficients.
