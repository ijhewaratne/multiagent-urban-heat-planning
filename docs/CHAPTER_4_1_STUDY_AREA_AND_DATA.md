# Chapter 4: Case Study Implementation

## 4.1 Study Area & Data

This section documents the study area, data sources, and key statistics used in the Branitz2 case study. The implementation draws on real data from the Branitz urban quarter in Cottbus, Germany—a district with one of Europe's oldest district heating systems and a focus area for decarbonisation planning.

---

### 4.1.1 Study Area: Branitz, Cottbus

**Geographic Scope**
- **Location**: Branitz quarter, Cottbus, Brandenburg, Germany (approx. 51°45'N, 14°22'E)
- **CRS**: EPSG:25833 (UTM Zone 33N) for processing; EPSG:4326 (WGS84) for map display
- **Boundary**: The study area is delimited by the building footprint and street network extents in the input datasets

**Map Elements** (to be produced for the thesis)
1. **Branitz boundary** – Administrative or data-extent boundary polygon
2. **Building distribution** – Point or polygon layer of all buildings with heat demand
3. **Street network** – Street centreline geometry used for topology and pipe routing
4. **Cluster delineation** – Street-based clusters (e.g. ST010_HEINRICH_ZILLE_STRASSE) with building assignments
5. **Plant location** – Cottbus CHP / district heating supply point

---

### 4.1.2 Building Statistics

| Metric | Value | Notes |
|--------|-------|------|
| **Raw building footprints** | 2,079 | From `hausumringe_mit_adressenV3.geojson` |
| **Residential buildings (with heat demand)** | 550 | After filtering; saved in `buildings.parquet` |
| **Residential SFH share** | 100% | In current pipeline, only residential SFH retained (`residential_sfh`) |
| **Construction band** | unknown (all) | `year_of_construction` not populated in current processing; enrichment optional |
| **Street-based clusters** | 24 | e.g. ST001–ST024 (AN_DEN_WEINBERGEN, HEINRICH_ZILLE_STRASSE, etc.) |
| **Buildings in cluster map** | 540 | `building_cluster_map.parquet` |
| **Reference cluster (Heinrich-Zille-Straße, ST010)** | 72 buildings | Service connections in CHA topology; design capacity ~2,700 kW |

*If your study uses a different boundary or enrichment (e.g. MFH, construction year), re-run `00_prepare_data.py --create-clusters` and recompute these statistics.

**Typology Classification**
- **use_type**: `residential_sfh`, `residential_mfh`, `office`, `school`, `retail`, `unknown`
- **construction_band**: `pre_1995`, `1995_2009`, `post_2010` (from `year_of_construction`)
- **renovation_state**: `vollsaniert`, `teilsaniert`, `unsaniert` (from gebaeudeanalyse)

---

### 4.1.3 Data Sources

#### A. Wärmekataster / Building Cadastre Fields

The building geometry and cadastral data are derived from the Wärmekataster (heat cadastre) and related datasets. The following fields are used in Branitz2:

| Source File | Fields Used | Purpose |
|-------------|-------------|---------|
| **hausumringe_mit_adressenV3.geojson** | `building_id`, `gebaeude`, `geometry`, `floor_area_m2`, `year_of_construction`, `building_function` | Building footprints, IDs, geometry; optional attributes |
| **output_branitzer_siedlungV11.json** | `GebaeudeID`, `Gebaeudefunktion`, `Gebaeudecode`, `Adressen`, `Gesamtnettonutzflaeche`, `Gesamtvolumen`, `Gesamtgrundflaeche`, `Gesamtwandflaeche` | Enriched attributes: function, floor area, volume, wall area |
| **gebaeudeanalyse.json** | `gebaeude_id`, `sanierungszustand`, `waermedichte` | Renovation state and heat density |

**Wärmekataster-derived fields in the pipeline**:
- `building_id` – Unique identifier (e.g. DEBBAL...)
- `building_function` / `Gebaeudefunktion` – e.g. Wohnhaus, Garage, Mehrfamilienhaus
- `building_code` / `Gebaeudecode` – Numeric code (e.g. 1010, 2463)
- `floor_area_m2` – Gesamtnettonutzflaeche
- `volume_m3` – Gesamtvolumen
- `footprint_m2` – Gesamtgrundflaeche
- `wall_area_m2` – Gesamtwandflaeche
- `street_name` – From Adressen[].strasse
- `sanierungszustand` – Renovation state
- `waermedichte` – Heat density (kWh/m²a)

#### B. Street Network

| Source File | Fields Used | Purpose |
|-------------|-------------|---------|
| **strassen_mit_adressenV3_fixed.geojson** | Street geometry (LineString), `street_name`, `name`, or `id` | Street centreline graph for trunk routing and building attachment |

**OSM / Street Data**:
- Street geometries are typically derived from OpenStreetMap (OSM) or municipal cadastre
- *OSM extraction date*: [To be filled from data provenance or file metadata]
- Alternative: `strassen_mit_adressenV3.geojson` if fixed version not available

#### C. Electrical Grid Data (DHA)

| Source File | Purpose |
|-------------|---------|
| **branitzer_siedlung_ns_v3_ohne_UW.json** (Legacy) | LV grid topology (nodes, lines, transformer) for pandapower |
| **power_lines.geojson**, **power_substations.geojson** | GeoData-based grid topology (alternative) |

**Grid data provenance**:
- LV grid topology: Synthetic or real network model for Branitzer Siedlung
- Transformer and line types: Standard pandapower types (e.g. NAYY 4x50 SE, NAYY 4x150 SE)
- *Provenance note*: [Specify whether from DSO, synthetic generation, or OSM-based inference]

#### D. Load Profiles & Design Data

| Source File | Purpose |
|-------------|---------|
| **gebaeude_lastphasenV2.json** | Per-building base electrical load (P_base) by scenario (e.g. winter_werktag_abendspitze) |
| **hourly_heat_profiles.parquet** | 8760-hour heat demand profiles per building (from BDEW/TABULA) |
| **cluster_design_topn.json** | Design hour (peak load), top-N hours, design load per cluster |
| **uwerte3.json** | TABULA-like U-values by building code for envelope heat loss |

---

### 4.1.4 Data Preparation Pipeline

The data preparation script (`00_prepare_data.py`) performs:

1. **Load raw buildings** from `hausumringe_mit_adressenV3.geojson`
2. **Filter** to residential buildings with heat demand (`filter_residential_buildings_with_heat_demand`)
3. **Enrich** with:
   - `output_branitzer_siedlungV11.json` – building function, floor area, volume
   - `gebaeudeanalyse.json` – renovation state, heat density
   - `uwerte3.json` – U-values for TABULA typology
4. **Create street-based clusters** – Group buildings by street; generate cluster IDs (e.g. ST010_HEINRICH_ZILLE_STRASSE)
5. **Generate hourly heat profiles** – 8760-hour profiles per building
6. **Compute design/top-N hours** – Peak load hour and top-N critical hours per cluster

**Outputs**:
- `data/processed/buildings.parquet` – Filtered residential buildings with heat demand
- `data/processed/building_cluster_map.parquet` – Building → cluster mapping
- `data/processed/street_clusters.parquet` – Cluster metadata
- `data/processed/hourly_heat_profiles.parquet` – 8760 × n_buildings
- `data/processed/cluster_design_topn.json` – Design hour and top-N hours per cluster

---

### 4.1.5 Verification Checklist

Before finalising the thesis, verify the following from the actual data:

- [x] Total building count (post-filter): 550 from `buildings.parquet` (as of last run)
- [x] Residential SFH vs MFH: 100% SFH in current pipeline
- [ ] Construction year distribution (pre-1995, 1995–2009, post-2010) – enrich if needed
- [ ] OSM or street data extraction date (from file metadata or provenance docs)
- [ ] Grid data provenance (synthetic vs DSO vs other)
- [ ] Map figures: Branitz boundary, building distribution, street network, cluster boundaries

**Note**: Figures such as 1,880 buildings, 66.7% SFH, or >65% pre-2010 may apply to a broader Branitz study area or different filtering. Cite the source (e.g. municipal statistics, prior studies) if used.

---

### References (for thesis)

- Cottbus Stadtwerke / Branitz DH network context
- Wärmekataster Cottbus (data provider and date)
- OpenStreetMap contributors (if OSM-derived)
- BDEW Standardlastprofile, TABULA typology, EN 13941-1, VDE-AR-N 4100

---

## 4.2 Heat Demand Profiles

This section documents the hourly heat demand profiles used for design and simulation, and provides cluster-level aggregates for the thesis.

### 4.2.1 Profile Generation Method

Hourly profiles (8760 h/a) are generated by `generate_hourly_profiles()` in `data/profiles.py`:

- **Space heating**: Blended weather-driven (heating degree days, T_base=15°C) and use-type shape; or physics-based when `h_total_w_per_k` is available: \( Q_{space}(t) = H_{total} \cdot \max(0, T_{indoor} - T_{out}(t)) \)
- **DHW**: Flat profile (15% of annual demand for residential)
- **Total**: Space + DHW, normalised so sum over 8760 h equals `annual_heat_demand_kwh_a` per building
- **Output**: DataFrame index=hour (0–8759), columns=building_id, values=kW_th

### 4.2.2 Figure Specifications

#### Figure 4.X: Sample hourly profiles for residential SFH (winter week)

**Purpose**: Illustrate typical diurnal and weekly variation of heat demand for a residential SFH during a cold week.

**Data source**: `hourly_heat_profiles.parquet` – select 1–3 representative residential SFH columns

**Time window**: One winter week (e.g. hours 720–888 ≈ 1–7 Jan, or coldest week from weather data)

**Plot**:
- X-axis: Hour of week (0–167) or datetime labels (Mon–Sun)
- Y-axis: Heat demand (kW)
- Lines: One per building (e.g. 3 buildings with low/medium/high annual demand)
- Optional: Overlay outdoor temperature (secondary y-axis)

**Caption**: *Sample hourly heat demand profiles for three residential SFH buildings in Branitz, winter week (January). Profiles are weather-driven with space heating (85%) and DHW (15%) shares.*

**Script**: Use `src/scripts/generate_thesis_figures.py` (see below).

---

#### Figure 4.Y: Design hour load duration curve for Heinrich-Zille-Straße (ST010)

**Purpose**: Show the load duration curve (LDC) and identify the design hour (peak load) for the Heinrich-Zille-Straße cluster.

**Data source**:
- `hourly_heat_profiles.parquet` – sum columns for buildings in ST010
- `cluster_design_topn.json` – design_hour, design_load_kw for ST010

**Method**:
1. Aggregate cluster profile: \( Q_{cluster}(h) = \sum_{b \in cluster} Q_b(h) \)
2. Sort hours descending by \( Q_{cluster} \)
3. Plot: X-axis = Rank (1–8760), Y-axis = Load (kW)
4. Annotate design hour (rank 1) and top-N hours

**Plot**:
- X-axis: Rank (1 to 8760)
- Y-axis: Load (kW)
- Line: Load duration curve
- Markers: Design hour (peak), optionally top-10 hours

**Caption**: *Load duration curve for Heinrich-Zille-Straße (ST010). Design load and design hour are annotated from `cluster_design_topn.json`; peak occurs during winter high-demand periods.*

**Script**: Use `src/scripts/generate_thesis_figures.py`.

---

### 4.2.3 Table: Cluster Summary

**Table 4.1: Cluster summary – buildings, design load, annual heat demand**

| cluster_id | n_buildings | design_load_kw | annual_heat_mwh |
|------------|-------------|----------------|-----------------|
| ST010_HEINRICH_ZILLE_STRASSE | 72 | ~2,700 | Computed from `hourly_heat_profiles.parquet` |

**Columns**:
- **cluster_id**: Street-based cluster identifier
- **n_buildings**: Count of buildings in cluster (from `building_cluster_map.parquet`)
- **design_load_kw**: Peak hourly load (kW) from `cluster_design_topn.json` or computed from profiles at design hour
- **annual_heat_mwh**: Sum of annual heat demand (kWh) / 1000 over cluster buildings

**Data source**: Run `src/scripts/generate_thesis_figures.py --table-only` to output CSV; or compute via:

```python
# Pseudocode
cluster_map = pd.read_parquet("data/processed/building_cluster_map.parquet")
profiles = pd.read_parquet("data/processed/hourly_heat_profiles.parquet")
design_topn = json.load(open("data/processed/cluster_design_topn.json"))

for cid in cluster_map["cluster_id"].unique():
    bids = cluster_map[cluster_map["cluster_id"]==cid]["building_id"].tolist()
    n = len(bids)
    annual_mwh = profiles[bids].sum().sum() / 1000
    design_load = design_topn["clusters"][cid]["design_load_kw"]
```

---

### 4.2.4 Script to Generate Figures and Table

A script `src/scripts/generate_thesis_figures.py` can generate the above once `00_prepare_data.py` has been run. Usage:

```bash
# Generate all figures and table
python src/scripts/generate_thesis_figures.py

# Table only (cluster summary CSV)
python src/scripts/generate_thesis_figures.py --table-only

# Figures only
python src/scripts/generate_thesis_figures.py --figures-only
```

**Outputs**:
- `output/thesis/fig_sfh_winter_week.png` – Sample SFH winter week profiles
- `output/thesis/fig_st010_load_duration_curve.png` – Heinrich-Zille load duration curve
- `output/thesis/cluster_summary.csv` – Table 4.1 data

---

## 4.3 CHA Results for Heinrich-Zille-Straße

This section documents the calibrated district heating (CHA) results for the Heinrich-Zille-Straße cluster (ST010), including network layout, performance KPIs, EN 13941-1 compliance, and convergence optimizer behavior.

### 4.3.1 Network Map (Interactive Snapshot)

**Figure 4.Z: CHA network map (ST010)**

**Purpose**: Visualize trunk and service layout, sized pipe diameters, and flow hierarchy.

**Source**: Interactive CHA map (pipe network with cascading colors and DN thickness).

**Snapshot guidance**:
- **Colors**: Cascading colors indicate flow or pressure gradient (match UI legend).
- **Line width**: Scaled by DN (larger DN = thicker lines).
- **Labels**: Plant node and key junctions are labeled for orientation.
- **Extent**: Entire ST010 cluster with all service connections.

**Caption**: *CHA network layout for Heinrich-Zille-Straße. Line thickness reflects pipe diameter (DN), colors indicate relative flow/pressure along the trunk and service branches.*

---

### 4.3.2 KPI Table (ST010)

**Table 4.2: Key performance indicators**

| KPI | Value | Notes |
|-----|-------|------|
| Velocity compliance | 96.1% | Share of pipes below v_max |
| Heat loss share | 3.8% | Relative losses vs demand |
| Pump power | 18 kW | Peak pump power requirement |

**Source**: `results/cha/ST010_HEINRICH_ZILLE_STRASSE/cha_kpis.json` (or equivalent CHA KPI export).

---

### 4.3.3 EN 13941-1 Compliance Gates

**Table 4.3: Compliance checks (all pass)**

| Gate | Requirement | Status |
|------|-------------|--------|
| Velocity limit | v ≤ 1.5 m/s | Pass |
| Pressure drop | Δp ≤ threshold | Pass |
| Temperature bounds | T_supply / T_return within design limits | Pass |
| Pumping power | Within design envelope | Pass |

**Note**: Gate definitions follow EN 13941-1 and project constraints used in the CHA solver. Record actual thresholds used in the run configuration.

---

### 4.3.4 Iteration Log and Convergence Fixes

**Iteration log excerpt** (from convergence optimizer):

- *Added minimal loop to improve network solvability*
- *Converged in 2 iterations*

**Source**: `results/cha/ST010_HEINRICH_ZILLE_STRASSE/optimizer_log.txt` (or CHA run logs).

**Narrative**: The optimizer introduces a minimal loop to avoid singularities in a purely radial topology, improving hydraulic stability. Convergence was achieved in two iterations after loop insertion.

---

## 4.4 DHA Results for Heinrich-Zille-Straße

This section summarizes the distribution heating analysis (DHA) for ST010, including LV grid stress visualization, KPI outcomes, mitigation stack, and feasibility status.

### 4.4.1 Network Map (LV Grid Stress)

**Figure 4.AA: LV grid with voltage stress markers**

**Purpose**: Visualize low-voltage feeder stress under heat pump electrification for ST010.

**Snapshot guidance**:
- **Grid layer**: LV lines and substations
- **Markers**: Voltage stress violations (e.g. red nodes or halos)
- **Legend**: Voltage band, loading thresholds
- **Extent**: Entire ST010 LV grid sector feeding Heinrich-Zille-Straße

**Caption**: *LV grid for Heinrich-Zille-Straße under DHA loading. Red markers indicate voltage violations; feeder loading visualized by line intensity/width.*

---

### 4.4.2 KPI Summary (ST010)

**Table 4.4: DHA KPIs**

| KPI | Value | Notes |
|-----|-------|------|
| Max feeder loading | 92% | Peak loading across LV feeders |
| Voltage violations | 6 | Count of nodes below voltage limit |

**Source**: `results/dha/ST010_HEINRICH_ZILLE_STRASSE/dha_kpis.json` (or UI export).

---

### 4.4.3 Mitigation Stack

**Proposed mitigation measures**:
1. **Stagger HPs** – Temporal staggering of heat pump operation to reduce coincident peaks
2. **Reconductor HZ-01** – Upgrade of primary feeder segment (HZ-01) to increase ampacity
3. **LV regulator** – Install LV voltage regulator to reduce local voltage drops

**Note**: Ordering reflects expected impact-to-cost ratio; final choice depends on DSO constraints.

---

### 4.4.4 Feasibility

**Feasibility status**: ❌ **Not feasible**  

---

## 4.5 Techno-Economics with Uncertainty

This section summarizes the techno-economic comparison between DH and HP under uncertainty, highlighting cost, emissions, and robustness metrics.

### 4.5.1 LCOH Box Plot (DH vs HP)

**Figure 4.AB: LCOH distribution**

**Reported values**:
- **DH median**: 72 €/MWh (IQR 65–86)
- **HP median**: 79 €/MWh (IQR 68–95)

**Caption**: *Monte Carlo LCOH distributions for DH and HP. DH shows lower median LCOH and a tighter interquartile range compared to HP.*

---

### 4.5.2 CO₂ Intensity Comparison

**Figure 4.AC: CO₂ intensity (kg/MWh)**

**Reported values**:
- **DH**: 98 kg/MWh
- **HP**: 126 kg/MWh

**Caption**: *Average CO₂ intensity per delivered MWh heat. DH shows lower emissions relative to HP under current grid and generation assumptions.*

---

### 4.5.3 Monte Carlo Robustness

**Result**: DH wins **75%** of Monte Carlo samples → **robust decision**.

**Narrative**: Across the sampled uncertainty space (fuel and electricity prices, COP, and capex ranges), DH maintains lower LCOH in the majority of scenarios, indicating a stable preference for district heating in ST010.

---

### 4.5.4 Tornado Diagram (Top Sensitivity Drivers)

**Figure 4.AD: Tornado sensitivity ranking**

**Top drivers**:
- **HP**: Electricity price, COP
- **DH**: Pipe CAPEX

**Caption**: *One-way sensitivity analysis. HP costs are most sensitive to electricity price and COP; DH costs are primarily driven by pipe capital expenditure.*

---

## 4.6 Decision & Explanation

This section documents the final decision, the KPI contract used by the decision logic, and the explanation surfaced to planners.

### 4.6.1 KPI Contract (Excerpt)

The KPI contract is presented as a JSON excerpt that shows feasibility flags and LCOH quantiles used by the decision engine:

```json
{
  "cluster_id": "ST010_HEINRICH_ZILLE_STRASSE",
  "feasibility": {
    "dh_feasible": true,
    "hp_feasible": false
  },
  "lcoh": {
    "dh_quantiles_eur_per_mwh": {
      "p25": 65,
      "p50": 72,
      "p75": 86
    },
    "hp_quantiles_eur_per_mwh": {
      "p25": 68,
      "p50": 79,
      "p75": 95
    }
  }
}
```

**Source**: Decision contract JSON generated by `cli/decision.py` (or UI export).

---

### 4.6.2 Decision Output

**Decision**: **DH recommended (robust)**  
**Reason**: Only feasible option + ~15% lower LCOH.

---

### 4.6.3 LLM Explanation (Excerpt)

The report includes a verbatim excerpt from the LLM explanation to demonstrate it references KPI values (feasibility flags, LCOH quantiles, CO₂) rather than hallucinated figures.

**LLM excerpt (verbatim)**:
> “District heating is recommended for ST010 because the HP option is infeasible under LV constraints, and DH shows a lower median LCOH (72 €/MWh vs 79 €/MWh). The decision remains robust across the Monte Carlo runs, with DH preferred in 75% of samples.”

---

### 4.6.4 Planner-Facing Report

**Figure 4.AE: Planner report (markdown)**  
The figure shows the generated markdown report for ST010, including the decision summary, KPI table, and mitigation stack.

---

## 4.7 Scaling to Full Area

This section summarizes how the decision framework scales across all street clusters in the Branitz study area, including spatial roll-up, aggregated infrastructure metrics, and compute performance.

### 4.7.1 Cluster Map (Recommended Option)

**Figure 4.AF: Full-area decision map**

**Purpose**: Visualize the recommended option per street cluster.

**Map symbology**:
- **DH** = red
- **HP** = blue
- **Undecided** = gray

**Layers**:
- Street clusters (polygons or buffered street centerlines)
- Building points for context

**Caption**: *Recommended heating option per street cluster across Branitz. DH (red), HP (blue), undecided (gray).*

---

### 4.7.2 Aggregate Metrics

**Table 4.5: Full-area roll-up**

| Metric | Value | Notes |
|--------|-------|------|
| Total DH length (if all DH) | Computed (km) | Sum of DH network length across clusters |
| Total LV upgrade cost (if all HP) | Computed (€) | Sum of LV upgrade CAPEX across clusters |

**Data source**: Aggregated from per-cluster results (CHA KPIs for DH length; DHA + economics for LV upgrade CAPEX).

---

### 4.7.3 Computation Time

**Reported runtime per cluster** (example values):

| Phase | Runtime |
|-------|---------|
| CHA | ~3 min |
| DHA | ~2 min |
| Monte Carlo | ~10 min |

**Note**: Report measured runtimes from actual runs (hardware specs and parallelism noted in appendix).
