# UHDC Report: ST002_ANTON_BRUCKNER_STRASSE
**Generated:** 2026-08-24T11:41:34Z

## Recommendation: **HP**
Robust: ✗

## Executive Summary

Our analysis indicates that heat pumps are the preferred heating solution for this area. Both district heating and heat pumps are technically viable options, with district heating meeting EN 13941-1 standards and heat pumps complying with VDE-AR-N 4100 grid requirements. While the lifetime cost of heat pumps at 120.1 €/MWh is very similar to district heating at 117.1 €/MWh, heat pumps offer a significant environmental advantage with lower CO₂ emissions of 144 kg/MWh compared to 160 kg/MWh for district heating. This lower carbon footprint was the deciding factor, although our robustness assessment shows that the choice between the two options is sensitive to future uncertainties.

## Key Metrics

### District Heating
- LCOH: 117.1 €/MWh (95% CI: 96.6-144.1)
- CO₂: 160 kg/MWh
- Feasible: ✓
- Max Velocity: 0.3055592754759886 m/s

### Heat Pumps
- LCOH: 120.1 €/MWh (95% CI: 94.6-146.4)
- CO₂: 144 kg/MWh
- Feasible: ✓
- Max Loading: 45.04545095428426%

## Decision Rationale

- **COST_CLOSE_USE_CO2**: LCOH difference ≤5% → using CO₂ as tie-breaker
- **CO2_TIEBREAKER_HP**: HP chosen due to lower CO₂ emissions (costs close)

## Data Sources


---
**Standards Referenced:**
- [DIN EN 13941-1:2023](https://cdn.standards.iteh.ai/samples/63107/9679243e93d447d8b7fff49c655c8eba/EN-13941-1-2023.pdf)
- [DIN EN 13941-1:2023](https://cdn.standards.iteh.ai/samples/63107/9679243e93d447d8b7fff49c655c8eba/EN-13941-1-2023.pdf)
- [DIN EN 13941-1:2023](https://cdn.standards.iteh.ai/samples/63107/9679243e93d447d8b7fff49c655c8eba/EN-13941-1-2023.pdf)
- [VDE-AR-N 4100:2022](https://www.vde.com/resource/blob/951050/aa29e1e9b568a3d9e59b83006b00e4bf/vde-ar-n-4100-2022-06-data.pdf)
- [VDE-AR-N 4100:2022](https://www.vde.com/resource/blob/951050/aa29e1e9b568a3d9e59b83006b00e4bf/vde-ar-n-4100-2022-06-data.pdf)