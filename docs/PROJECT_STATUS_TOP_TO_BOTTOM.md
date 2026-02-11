# Branitz2 Project Status: Top to Bottom

**Date**: 2026-01-25  
**Purpose**: Single reference for current implementation state, data expectations, and runnability.

---

## 1. Project Identity & Scope

- **Name**: Branitz Heat Decision AI System (Branitz2)
- **Goal**: Deterministic, auditable framework for street-level heat planning (DH vs HP) in Branitz, Cottbus.
- **Stack**: Python 3.10+, Streamlit UI, pandapipes (DH), pandapower (LV), optional Gemini LLM for explanations.
- **Standards**: EN 13941-1 (DH), VDE-AR-N 4100 (LV).

---

## 2. Repository Layout

```
Branitz2/
├── config/                    # Decision scenario configs (2023, 2030, aggressive)
├── data/
│   ├── raw/                   # Expected: Wärmekataster, streets, enrichment (see §3)
│   └── processed/             # Output of 00_prepare_data (parquet, JSON)
├── docs/                      # 15+ .md (thesis Ch4, validation, economics, DHA, etc.)
├── Legacy/                    # Reference data & old implementations (not main pipeline)
│   ├── CHA/                   # Legacy CHA scripts
│   ├── DHA/HP New/Data/       # branitzer_siedlung_ns_v3_ohne_UW.json, output_branitzer_siedlungV11, etc.
│   └── fromDifferentThesis/   # gebaeudedaten (geojson, uwerte3, gebaeudeanalyse, etc.)
├── results/                   # All pipeline outputs: cha/, dha/, economics/, decision/, uhdc/
├── scripts/                   # Standalone helpers (check_heinrich_zille, generate_map, etc.)
├── src/
│   ├── branitz_heat_decision/ # Main package
│   │   ├── adk/               # Agent Development Kit (agent, tools, policies)
│   │   ├── case_studies/      # Heinrich-Zille config
│   │   ├── cha/               # District heating network (pandapipes)
│   │   ├── cli/               # decision, economics, uhdc entry points
│   │   ├── config/            # Paths, validation_standards
│   │   ├── data/              # Loader, profiles, cluster, typology
│   │   ├── decision/          # KPI contract, rules, schemas
│   │   ├── dha/               # LV grid hosting (pandapower)
│   │   ├── economics/         # LCOH, CO₂, Monte Carlo, sensitivity
│   │   ├── uhdc/              # Explainer, report_builder, safety_validator, orchestrator
│   │   ├── ui/                # Streamlit app, services, registry, llm
│   │   └── validation/        # TNLI logic auditor, claims, feedback
│   └── scripts/               # Pipeline scripts (00–03, generate_thesis_figures, serve_maps)
├── pyproject.toml
├── requirements.txt
├── fullSystem.md              # Full system doc (architecture, agents, validation)
├── architecture_overview.md   # UI/Agent/Script mapping
└── README.md
```

---

## 3. Data Status & Expectations

### 3.1 Raw Data (required for full pipeline)

Pipeline expects **`data/raw/`** (or `$BRANITZ_DATA_ROOT/raw`). Repo ships **only** `.gitkeep` in `data/raw/` and `data/processed/`.

| File | Purpose | Where it lives if not in data/raw |
|------|---------|-----------------------------------|
| hausumringe_mit_adressenV3.geojson | Building footprints | Legacy/fromDifferentThesis/gebaeudedaten/ |
| strassen_mit_adressenV3_fixed.geojson | Street centerlines | (create from OSM or use variant) |
| output_branitzer_siedlungV11.json | Building attributes | Legacy/fromDifferentThesis/gebaeudedaten/ or Legacy/DHA/HP New/Data/ |
| gebaeudeanalyse.json | Sanierungszustand, waermedichte | Legacy/fromDifferentThesis/gebaeudedaten/ |
| uwerte3.json | U-values by building code | Legacy/fromDifferentThesis/gebaeudedaten/ |
| weather.parquet | 8760 h temperatures | Must be provided or generated |
| gebaeude_lastphasenV2.json | Base electrical loads (DHA) | Legacy/DHA/HP New/Data/ or Legacy/fromDifferentThesis/ |
| branitzer_siedlung_ns_v3_ohne_UW.json | LV grid topology (DHA) | Legacy/DHA/HP New/Data/ |
| (optional) Technikkatalog*.xlsx | Pipe catalog (CHA) | data/raw/ (01_run_cha looks for specific names) |
| (optional) bdew_profiles.csv, bdew_slp_gebaeudefunktionen.json, building_population_resultsV6.json | BDEW/DHA | data/raw or Legacy/fromDifferentThesis/load-profile-generator |

**Action**: Copy or symlink from `Legacy/` into `data/raw/` (and add `weather.parquet`) to run the full pipeline.

### 3.2 Processed Data (output of 00_prepare_data)

After running `00_prepare_data.py` with `--create-clusters`:

| Path | Description |
|------|-------------|
| data/processed/buildings.parquet | Filtered residential buildings with heat demand |
| data/processed/building_cluster_map.parquet | building_id → cluster_id |
| data/processed/street_clusters.parquet | Cluster metadata + geometry |
| data/processed/hourly_heat_profiles.parquet | 8760 × n_buildings (kW) |
| data/processed/cluster_design_topn.json | Design hour, design_load_kw, top-N per cluster |
| data/processed/cluster_ui_index.parquet | UI cluster list/summary |
| data/processed/weather.parquet | Used by 00; must exist for profile generation |

**Current state**: `data/processed/` contains only `.gitkeep` unless the user has run `00_prepare_data.py` with raw data in place.

---

## 4. Pipeline Scripts (Execution Order)

| Step | Script | Purpose | Depends on |
|------|--------|---------|------------|
| 0 | `00_prepare_data.py` | Load raw → filter → enrich → cluster → profiles → design/top-N → cluster_ui_index | data/raw/*, weather.parquet |
| 1 | `01_run_cha.py` | DH network (trunk-spur), sizing, pandapipes, KPIs, maps | processed/*, optional pipe catalog |
| 2 | `02_run_dha.py` | LV hosting capacity, powerflow, violations, hp_lv_map | processed/*, LV grid JSON, base loads |
| 3 | `03_run_economics.py` | LCOH, CO₂, Monte Carlo, sensitivity, stress tests | CHA + DHA KPIs, processed/* |
| – | `cli/decision.py` | KPI contract → decision → (optional) LLM explanation | CHA, DHA, Economics results |
| – | `cli/uhdc.py` | Stakeholder HTML/MD report | Decision outputs |
| – | `generate_thesis_figures.py` | Thesis figures + cluster summary CSV | processed/* (profiles, design_topn, cluster_map) |

- **01_run_cha_trunk_spur.py**: Deprecated as standalone; use `01_run_cha.py --use-trunk-spur`.
- **01_run_cha_with_validation.py**: Validation-focused CHA run.
- **04_make_decision.py** / **05_generate_report.py**: Deprecated; use `cli/decision.py` and `cli/uhdc.py`.
- **serve_maps.py**: Not implemented (placeholder).

---

## 5. Module Status (Implementation)

| Module | Status | Notes |
|--------|--------|------|
| **data/** | ✅ | Loader, filter, profiles, cluster, typology; Legacy-aligned fallbacks where needed |
| **cha/** | ✅ | Trunk-spur network builder, sizing catalog, convergence optimizer, heat loss, KPI extractor, EN 13941-1 checks |
| **dha/** | ✅ | LV grid from legacy JSON or geodata, BDEW base loads, loadflow, hosting capacity, mitigations, KPI extractor |
| **economics/** | ✅ | LCOH (DH/HP), CO₂, Monte Carlo, sensitivity, stress tests; marginal plant allocation; LV upgrade cost from DHA |
| **decision/** | ✅ | KPI contract builder, rules engine, schemas, decide_from_contract |
| **uhdc/** | ✅ | LLM explainer (Gemini), template fallback, safety_validator (TNLI), report_builder (HTML/MD), orchestrator |
| **validation/** | ✅ | Logic auditor, claims, TNLI-style checks; integration with explainer |
| **cli/** | ✅ | decision, economics, uhdc; --llm-explanation, --no-fallback, batch --all-clusters |
| **ui/** | ✅ | Streamlit app (6 tabs), services (ClusterService, JobService, ResultService), registry (scenario commands), LLM router |
| **adk/** | ✅ | Agent, tools (run CHA/DHA/Econ/Decision/UHDC), policies |

---

## 6. Configuration & Environment

- **Paths**: `src/branitz_heat_decision/config/__init__.py` — `DATA_ROOT = os.getenv("BRANITZ_DATA_ROOT", PROJECT_ROOT / "data")`, so `data/raw` and `data/processed` are under `DATA_ROOT`.
- **Results**: `RESULTS_ROOT = PROJECT_ROOT / "results"`; per-cluster: `results/{cha|dha|economics|decision|uhdc}/{cluster_id}/`.
- **Optional .env**: `GOOGLE_API_KEY`, `GOOGLE_MODEL`, `LLM_TIMEOUT`, `UHDC_FORCE_TEMPLATE` for LLM explanations.
- **README** mentions `environment.yml` for conda; repo has **requirements.txt** only (no `environment.yml` in tree). Use `pip install -r requirements.txt` or create conda env manually.

---

## 7. UI (Streamlit)

- **Entry**: `streamlit run src/branitz_heat_decision/ui/app.py`
- **Cluster list**: From `data/processed/cluster_ui_index.parquet` (built by 00_prepare_data). If missing, cluster dropdown is empty.
- **Tabs**: Overview, Feasibility (CHA/DHA), Economics, Compare & Decide, Portfolio, Jobs.
- **Scenario runs**: Registry in `ui/registry.py` defines CLI commands for CHA, DHA, Economics, Decision, UHDC; JobService runs them as subprocesses and ResultService discovers artifacts under `results/`.

---

## 8. Key Integrations & Fixes (Recent)

- **Economics ↔ DHA**: `03_run_economics.py` loads `max_feeder_loading_pct` from DHA KPIs (flat or nested schema); LV upgrade cost and feeder loading drive economics.
- **Safety validator**: UHDC explainer runs TNLI Logic Auditor on LLM output; on violation, falls back to template and logs.
- **Report**: Interactive map and box plots removed from report; LLM is default for executive summary when generating md/html; `--template-only` forces template-only.
- **LCOH**: Marginal plant allocation and “no plant context” handling fixed in economics integration.

---

## 9. Documentation

- **fullSystem.md**: Full architecture, agents, validation, long reference.
- **architecture_overview.md**: UI → JobService → Scripts, Agent–Script mapping.
- **docs/**: CHAPTER_4_1_STUDY_AREA_AND_DATA.md (thesis Ch 4.1–4.7), BRANITZ2_VS_DISTRICTHEATINGSIM_TABLE.md, decision_pipeline, economics, validation_methods, DHA mitigations, workflow_ui_to_agents, etc.
- **Per-module**: cha_readme, dha_readme, economics_readme, decision_readme, uhdc_readme, cli_readme, ui_readme, data_readme, scripts_readme.

---

## 10. Gaps & To-Do (Summary)

1. **Data**: `data/raw/` is empty in repo; user must supply or link Legacy data and weather so 00_prepare_data and downstream scripts run.
2. **Weather**: `weather.parquet` (8760 h) must exist for profile generation; not auto-generated in repo.
3. **environment.yml**: Referenced in README but not present; document pip/conda install from requirements.txt.
4. **Cluster index**: UI needs `cluster_ui_index.parquet` from 00_prepare_data; no cluster list until that is run.
5. **serve_maps.py**: Placeholder only.
6. **Full-area run**: 4.7 thesis metrics (total DH length, total LV cost, runtimes) are placeholders until batch runs are executed and aggregated.

---

## 11. How to Run (Minimal)

1. **Prepare data** (once raw data and weather are in place):
   ```bash
   export BRANITZ_DATA_ROOT=/path/to/project  # or leave default = project/data
   # Ensure data/raw has: buildings geojson, streets, output_branitzer_siedlungV11.json,
   #   gebaeudeanalyse.json, uwerte3.json, weather.parquet (8760 rows)
   PYTHONPATH=src python src/scripts/00_prepare_data.py --create-clusters
   ```
2. **Single cluster (e.g. ST010)**:
   ```bash
   PYTHONPATH=src python src/scripts/01_run_cha.py --cluster-id ST010_HEINRICH_ZILLE_STRASSE --use-trunk-spur --optimize-convergence
   PYTHONPATH=src python src/scripts/02_run_dha.py --cluster-id ST010_HEINRICH_ZILLE_STRASSE
   PYTHONPATH=src python src/scripts/03_run_economics.py --cluster-id ST010_HEINRICH_ZILLE_STRASSE
   PYTHONPATH=src python -m branitz_heat_decision.cli.decision --cluster-id ST010_HEINRICH_ZILLE_STRASSE
   ```
3. **UI**:
   ```bash
   streamlit run src/branitz_heat_decision/ui/app.py
   ```
4. **Thesis figures + table** (after 00_prepare_data):
   ```bash
   PYTHONPATH=src python src/scripts/generate_thesis_figures.py
   ```

---

## 12. One-Sentence Summary

**Branitz2 is a fully implemented multi-agent heat-planning pipeline (data → CHA → DHA → Economics → Decision → UHDC reports) with a Streamlit UI and optional LLM explanations; it is runnable end-to-end once raw data and weather are placed under `data/raw/` and `00_prepare_data.py` has been run.**
