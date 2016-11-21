
## Santos
### Probe performance data

Values based on 47k measurement resistor.
![Sensor performance chart](Santos_resolution.png)

Property | Symbol | Value
-------- | -------- | --------
Resistance at 0°C | R<sub>25</sub> | 728.04k
Resistance at 25°C | R<sub>25</sub> | 200.48k
Resistance at 85°C | R<sub>25</sub> | 17.44k
Beta 25°C to 85°C | B<sub>25/85</sub>| 4346K
Minimum measurable temperature | | 264.7°C
Minimum high-res temperature | | -5.9°C
Highest resolution || 2.42e-02°C/step at 51.7°C
Maximum high-res temperature | | 125.3°C
Maximum measurable temperature | | -40.4°C

### Probe curve data
![Probe fit chart](Santos_curve.png)

Property | Symbol | Value
-------- | -------- | --------
Resistance near 25°C | R<sub>25</sub><sup>1</sup> | 200.82k
Steinhart-Hart coefficient | a | 3.3561093e-03 ± 1.7524253e-07
Steinhart-Hart coefficient | b | 2.3552814e-04 ± 1.1801451e-07
Steinhart-Hart coefficient | c | 2.1375541e-06 ± 1.9662826e-08

<sup>1</sup>: The deviation between this R<sub>25</sub> and the R<sub>25</sub> shown above is not relevant, this R<sub>25</sub> is taken from the original data point which is closest to 25°C. The value taken as a factor into the calculation of the final value and serves only a scaling purpose to the Steinhart-Hart coefficients.
