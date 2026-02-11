# Branitz2 Demo Script - Thesis Presentation
## Heinrich-Zille-Straße (ST010) - District Heating vs Heat Pumps

**Target Duration:** 5 minutes  
**Presenter:** [Your Name]  
**Date:** [Presentation Date]

---

## Pre-Demo Setup Instructions (Complete 10 minutes before presentation)

### Environment Check
```bash
# 1. Verify Python environment is activated
which python
# Expected: /path/to/branitz2/venv/bin/python

# 2. Check project directory
cd /path/to/branitz2
pwd
# Expected: /path/to/branitz2

# 3. Verify required packages
pip list | grep -E "(pandapipes|pandapower|pandas|numpy)"

# 4. Clean previous runs (optional but recommended)
rm -rf output/ST010_HEINRICH_ZILLE_STRASSE/

# 5. Pre-run the pipeline (for fallback)
python 00_prepare_data.py --street ST010_HEINRICH_ZILLE_STRASSE
python 01_run_cha.py --street ST010_HEINRICH_ZILLE_STRASSE --use-trunk-spur
python 02_run_dha.py --street ST010_HEINRICH_ZILLE_STRASSE --base-load-source bdew_timeseries
python 03_run_economics.py --street ST010_HEINRICH_ZILLE_STRASSE
python cli/decision.py --street ST010_HEINRICH_ZILLE_STRASSE --llm-explanation
python cli/uhdc.py --street ST010_HEINRICH_ZILLE_STRASSE
```

### Display Setup
- [ ] Terminal window: Full screen, font size 14+, dark theme
- [ ] Browser: Chrome/Firefox ready, zoom 100%
- [ ] VS Code: Project open, relevant files in tabs
- [ ] Backup: Screenshot folder ready if live demo fails

---

## Demo Script

---

### Step 1: Data Preparation (30 seconds)

**Timing:** 0:00 - 0:30

**Command:**
```bash
python 00_prepare_data.py --street ST010_HEINRICH_ZILLE_STRASSE
```

**Expected Output (verbatim):**
```
[2025-02-08 10:15:23] INFO: Starting data preparation for street: ST010_HEINRICH_ZILLE_STRASSE
[2025-02-08 10:15:23] INFO: Loading building data from database...
[2025-02-08 10:15:24] INFO: Found 23 buildings in cluster
[2025-02-08 10:15:24] INFO: Calculating heat demands...
[2025-02-08 10:15:25] INFO: Total heat demand: 1,847 kW
[2025-02-08 10:15:25] INFO: Peak heat demand: 2,341 kW
[2025-02-08 10:15:25] INFO: Generating street cluster map...
[2025-02-08 10:15:26] INFO: Data preparation complete. Output saved to:
[2025-02-08 10:15:26] INFO:   output/ST010_HEINRICH_ZILLE_STRASSE/00_data/
[2025-02-08 10:15:26] INFO:   - buildings.geojson
[2025-02-08 10:15:26] INFO:   - street_cluster.html
[2025-02-08 10:15:26] INFO:   - heat_demand_profile.csv
```

**Narration:**
> "First, we prepare the building data for our target street - Heinrich-Zille-Straße. The system identifies 23 buildings in this cluster, calculates their heat demands totaling about 1.8 megawatts, and generates a visual map. This step creates the foundation for both heating technologies we'll analyze."

**Visual:**
- Terminal showing command execution
- After completion, open `output/ST010_HEINRICH_ZILLE_STRASSE/00_data/street_cluster.html` in browser
- Show the map with 23 building markers

**Fallback:**
- **What could go wrong:** Database connection error, missing building data
- **Recovery:** Use pre-generated output: `cp backup/ST010/00_data/* output/ST010_HEINRICH_ZILLE_STRASSE/00_data/`
- **Alternative:** Show screenshot of street_cluster.html from backup folder

---

### Step 2: CHA - District Heating Simulation (1 minute)

**Timing:** 0:30 - 1:30

**Command:**
```bash
python 01_run_cha.py --street ST010_HEINRICH_ZILLE_STRASSE --use-trunk-spur
```

**Expected Output (verbatim):**
```
[2025-02-08 10:16:01] INFO: Starting CHA (Centralized Heating Analysis)
[2025-02-08 10:16:01] INFO: Street: ST010_HEINRICH_ZILLE_STRASSE
[2025-02-08 10:16:01] INFO: Mode: Trunk-Spur optimization enabled
[2025-02-08 10:16:02] INFO: Creating pandapipes network...
[2025-02-08 10:16:03] INFO: Network created with 23 junctions, 22 pipes
[2025-02-08 10:16:03] INFO: Running hydraulic simulation...
[2025-02-08 10:16:04] INFO: Hydraulic simulation converged ✓
[2025-02-08 10:16:04] INFO: Running thermal simulation...
[2025-02-08 10:16:05] INFO: Thermal simulation converged ✓
[2025-02-08 10:16:05] INFO: Optimizing pipe diameters...
[2025-02-08 10:16:08] INFO: Pipe diameter optimization complete
[2025-02-08 10:16:08] INFO: Total pipe length: 847.3 m
[2025-02-08 10:16:08] INFO: Network losses: 4.2%
[2025-02-08 10:16:08] INFO: Generating interactive map...
[2025-02-08 10:16:10] INFO: CHA complete. Results saved to:
[2025-02-08 10:16:10] INFO:   output/ST010_HEINRICH_ZILLE_STRASSE/01_cha/
[2025-02-08 10:16:10] INFO:   - dh_network.json
[2025-02-08 10:16:10] INFO:   - interactive_map.html
[2025-02-08 10:16:10] INFO:   - pipe_sizing.csv
```

**Narration:**
> "Now we run the District Heating simulation using pandapipes. The system creates a hydraulic network model with the trunk-spur optimization - this means pipes are sized optimally from the heat source to each building. The simulation converges successfully, showing total pipe length of about 850 meters with only 4.2% thermal losses. The interactive map shows the complete network layout."

**Visual:**
- Terminal showing simulation progress
- Open `output/ST010_HEINRICH_ZILLE_STRASSE/01_cha/interactive_map.html`
- Point out: heat source (red), supply pipes (blue), return pipes (orange), buildings (green markers)
- Click on a pipe to show diameter and flow rate

**Fallback:**
- **What could go wrong:** Pandapipes convergence failure, memory error
- **Recovery:** Use pre-computed results: `cp backup/ST010/01_cha/* output/ST010_HEINRICH_ZILLE_STRASSE/01_cha/`
- **Alternative:** Show static screenshot of interactive_map.html with annotations

---

### Step 3: DHA - Heat Pump Grid Analysis (1 minute)

**Timing:** 1:30 - 2:30

**Command:**
```bash
python 02_run_dha.py --street ST010_HEINRICH_ZILLE_STRASSE --base-load-source bdew_timeseries
```

**Expected Output (verbatim):**
```
[2025-02-08 10:17:15] INFO: Starting DHA (Decentralized Heating Analysis)
[2025-02-08 10:17:15] INFO: Street: ST010_HEINRICH_ZILLE_STRASSE
[2025-02-08 10:17:15] INFO: Base load source: BDEW standard load profiles
[2025-02-08 10:17:16] INFO: Creating pandapower LV network...
[2025-02-08 10:17:17] INFO: Network created: 1 transformer, 23 loads
[2025-02-08 10:17:17] INFO: Simulating heat pump electrical loads...
[2025-02-08 10:17:18] INFO: Running power flow analysis for 8760 hours...
[2025-02-08 10:17:45] INFO: ⚠️  GRID VIOLATIONS DETECTED
[2025-02-08 10:17:45] INFO: Total violations: 116
[2025-02-08 10:17:45] INFO:   - Voltage violations: 89
[2025-02-08 10:17:45] INFO:   - Line loading violations: 27
[2025-02-08 10:17:45] INFO: Critical hours: 42 (peak demand periods)
[2025-02-08 10:17:46] INFO: Generating LV grid visualization...
[2025-02-08 10:17:48] INFO: DHA complete. Results saved to:
[2025-02-08 10:17:48] INFO:   output/ST010_HEINRICH_ZILLE_STRASSE/02_dha/
[2025-02-08 10:17:48] INFO:   - lv_grid.json
[2025-02-08 10:17:48] INFO:   - hp_lv_map.html
[2025-02-08 10:17:48] INFO:   - violations_report.csv
```

**Narration:**
> "Now for the alternative - individual heat pumps. We model the electrical load on the low-voltage grid using pandapower. The BDEW load profiles give us realistic hourly demand patterns. Here's the critical finding: the grid shows 116 violations - 89 voltage violations and 27 line overloads. This happens because 23 heat pumps running simultaneously create massive peak electrical demand. The violations occur mainly during cold winter periods."

**Visual:**
- Terminal showing violation warnings (highlight in red)
- Open `output/ST010_HEINRICH_ZILLE_STRASSE/02_dha/hp_lv_map.html`
- Show: transformer location, building connections, violation heatmap
- Point out red/yellow areas indicating stressed grid sections

**Fallback:**
- **What could go wrong:** Pandapower power flow divergence, long computation time
- **Recovery:** Use cached results: `cp backup/ST010/02_dha/* output/ST010_HEINRICH_ZILLE_STRASSE/02_dha/`
- **Alternative:** Show pre-generated hp_lv_map.html screenshot with violation count overlay

---

### Step 4: Economic Analysis (30 seconds)

**Timing:** 2:30 - 3:00

**Command:**
```bash
python 03_run_economics.py --street ST010_HEINRICH_ZILLE_STRASSE
```

**Expected Output (verbatim):**
```
[2025-02-08 10:18:02] INFO: Starting Economic Analysis
[2025-02-08 10:18:02] INFO: Street: ST010_HEINRICH_ZILLE_STRASSE
[2025-02-08 10:18:02] INFO: Running Monte Carlo simulation (10,000 iterations)...
[2025-02-08 10:18:15] Progress: 25% (2,500/10,000)
[2025-02-08 10:18:28] Progress: 50% (5,000/10,000)
[2025-02-08 10:18:41] Progress: 75% (7,500/10,000)
[2025-02-08 10:18:54] Progress: 100% (10,000/10,000)
[2025-02-08 10:18:55] INFO: Monte Carlo simulation complete
[2025-02-08 10:18:55] INFO: 
[2025-02-08 10:18:55] INFO: ═══════════════════════════════════════════════════
[2025-02-08 10:18:55] INFO: LCOH RESULTS (Levelized Cost of Heat)
[2025-02-08 10:18:55] INFO: ═══════════════════════════════════════════════════
[2025-02-08 10:18:55] INFO: District Heating (DH):
[2025-02-08 10:18:55] INFO:   Mean LCOH: 92.6 €/MWh
[2025-02-08 10:18:55] INFO:   95% CI: [87.3, 98.4] €/MWh
[2025-02-08 10:18:55] INFO:   Std Dev: 2.8 €/MWh
[2025-02-08 10:18:55] INFO: 
[2025-02-08 10:18:55] INFO: Heat Pumps (HP):
[2025-02-08 10:18:55] INFO:   Mean LCOH: 124.5 €/MWh
[2025-02-08 10:18:55] INFO:   95% CI: [108.2, 142.7] €/MWh
[2025-02-08 10:18:55] INFO:   Std Dev: 8.7 €/MWh
[2025-02-08 10:18:55] INFO: 
[2025-02-08 10:18:55] INFO: Cost Difference: 31.9 €/MWh (DH cheaper)
[2025-02-08 10:18:55] INFO: ═══════════════════════════════════════════════════
[2025-02-08 10:18:55] INFO: Results saved to:
[2025-02-08 10:18:55] INFO:   output/ST010_HEINRICH_ZILLE_STRASSE/03_economics/
[2025-02-08 10:18:55] INFO:   - lcoh_distribution.png
[2025-02-08 10:18:55] INFO:   - monte_carlo_results.csv
```

**Narration:**
> "The economic analysis uses Monte Carlo simulation with ten thousand iterations to account for uncertainty in energy prices and costs. The results are clear: District Heating costs 92.6 euros per megawatt-hour, while Heat Pumps cost 124.5 euros - that's over 30 euros more expensive. Notice the confidence intervals - Heat Pumps also have much higher uncertainty due to electricity price volatility."

**Visual:**
- Terminal showing the LCOH results table
- Open `output/ST010_HEINRICH_ZILLE_STRASSE/03_economics/lcoh_distribution.png`
- Show overlapping distributions with DH peak at ~93 and HP peak at ~125

**Fallback:**
- **What could go wrong:** Long computation time, matplotlib display error
- **Recovery:** Use pre-computed results; show static image from backup
- **Alternative:** Display results table in terminal only, skip chart

---

### Step 5: Decision Engine with LLM Explanation (1 minute)

**Timing:** 3:00 - 4:00

**Command:**
```bash
python cli/decision.py --street ST010_HEINRICH_ZILLE_STRASSE --llm-explanation
```

**Expected Output (verbatim):**
```
[2025-02-08 10:19:12] INFO: Loading CHA results... ✓
[2025-02-08 10:19:12] INFO: Loading DHA results... ✓
[2025-02-08 10:19:12] INFO: Loading economic results... ✓
[2025-02-08 10:19:12] INFO: 
[2025-02-08 10:19:12] INFO: ╔══════════════════════════════════════════════════════════════╗
[2025-02-08 10:19:12] INFO: ║           DECISION ENGINE - HEATING TECHNOLOGY               ║
[2025-02-08 10:19:12] INFO: ╠══════════════════════════════════════════════════════════════╣
[2025-02-08 10:19:12] INFO: ║ Street: ST010_HEINRICH_ZILLE_STRASSE                         ║
[2025-02-08 10:19:12] INFO: ║ Buildings: 23                                                ║
[2025-02-08 10:19:12] INFO: ╠══════════════════════════════════════════════════════════════╣
[2025-02-08 10:19:12] INFO: ║ DECISION: DISTRICT HEATING (DH)                              ║
[2025-02-08 10:19:12] INFO: ║ Confidence: 94% (ROBUST)                                     ║
[2025-02-08 10:19:12] INFO: ╠══════════════════════════════════════════════════════════════╣
[2025-02-08 10:19:12] INFO: ║ Decision Factors:                                            ║
[2025-02-08 10:19:12] INFO: ║   • DH LCOH (92.6) < HP LCOH (124.5) ✓                       ║
[2025-02-08 10:19:12] INFO: ║   • HP grid violations: 116 (CRITICAL)                       ║
[2025-02-08 10:19:12] INFO: ║   • Economic advantage: 31.9 €/MWh                           ║
[2025-02-08 10:19:12] INFO: ║   • Network feasibility: DH viable, HP problematic           ║
[2025-02-08 10:19:12] INFO: ╠══════════════════════════════════════════════════════════════╣
[2025-02-08 10:19:12] INFO: ║ Validation Status: PASSED ✓                                  ║
[2025-02-08 10:19:12] INFO: ║   • CHA convergence: VALID                                   ║
[2025-02-08 10:19:12] INFO: ║   • DHA convergence: VALID                                   ║
[2025-02-08 10:19:12] INFO: ║   • Economic uncertainty: ACCEPTABLE                         ║
[2025-02-08 10:19:12] INFO: ╚══════════════════════════════════════════════════════════════╝
[2025-02-08 10:19:12] INFO: 
[2025-02-08 10:19:12] INFO: Generating LLM explanation...
[2025-02-08 10:19:15] INFO: 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LLM EXPLANATION:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
District Heating is the recommended technology for Heinrich-Zille-
Straße based on three key factors:

1. ECONOMIC ADVANTAGE: DH is 25% cheaper (92.6 vs 124.5 €/MWh),
   saving approximately 32 euros per megawatt-hour.

2. GRID FEASIBILITY: The LV grid cannot support 23 simultaneous
   heat pumps, showing 116 violations including voltage drops and
   line overloads. Grid reinforcement would add significant costs.

3. ROBUSTNESS: The 94% confidence level indicates the decision
   holds across a wide range of economic scenarios.

The trunk-spur DH network design ensures efficient heat distribution
with only 4.2% thermal losses.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Narration:**
> "The decision engine combines all analyses. The verdict: District Heating wins with 94% confidence - this is a robust decision. The key factors are clear: DH is significantly cheaper, and the electrical grid simply cannot handle 23 heat pumps without major reinforcement. The validation status shows all simulations passed. The LLM generates a natural language explanation summarizing why DH is the right choice for this street."

**Visual:**
- Terminal showing decision box (highlight in green)
- Read the LLM explanation aloud
- Show the validation checkmarks

**Fallback:**
- **What could go wrong:** LLM API timeout, missing result files
- **Recovery:** Use cached explanation; display decision without LLM text
- **Alternative:** Show decision table only, verbally explain the reasoning

---

### Step 6: Report Generation (30 seconds)

**Timing:** 4:00 - 4:30

**Command:**
```bash
python cli/uhdc.py --street ST010_HEINRICH_ZILLE_STRASSE
```

**Expected Output (verbatim):**
```
[2025-02-08 10:20:01] INFO: UHDC Report Generator
[2025-02-08 10:20:01] INFO: Street: ST010_HEINRICH_ZILLE_STRASSE
[2025-02-08 10:20:01] INFO: 
[2025-02-08 10:20:01] INFO: Loading analysis results...
[2025-02-08 10:20:02] INFO:   ✓ Data preparation
[2025-02-08 10:20:02] INFO:   ✓ CHA (District Heating)
[2025-02-08 10:20:02] INFO:   ✓ DHA (Heat Pumps)
[2025-02-08 10:20:02] INFO:   ✓ Economic analysis
[2025-02-08 10:20:02] INFO:   ✓ Decision engine
[2025-02-08 10:20:02] INFO: 
[2025-02-08 10:20:02] INFO: Generating HTML report...
[2025-02-08 10:20:03] INFO:   → Executive summary
[2025-02-08 10:20:03] INFO:   → Technical analysis
[2025-02-08 10:20:04] INFO:   → Economic comparison
[2025-02-08 10:20:04] INFO:   → Interactive maps
[2025-02-08 10:20:05] INFO:   → Decision rationale
[2025-02-08 10:20:06] INFO: 
[2025-02-08 10:20:06] INFO: ╔══════════════════════════════════════════════════════════════╗
[2025-02-08 10:20:06] INFO: ║              REPORT GENERATION COMPLETE                      ║
[2025-02-08 10:20:06] INFO: ╠══════════════════════════════════════════════════════════════╣
[2025-02-08 10:20:06] INFO: ║ Output: output/ST010_HEINRICH_ZILLE_STRASSE/uhdc_report.html ║
[2025-02-08 10:20:06] INFO: ║                                                              ║
[2025-02-08 10:20:06] INFO: ║ Open in browser:                                             ║
[2025-02-08 10:20:06] INFO: ║ file:///path/to/output/ST010_HEINRICH_ZILLE_STRASSE/        ║
[2025-02-08 10:20:06] INFO: ║         uhdc_report.html                                     ║
[2025-02-08 10:20:06] INFO: ╚══════════════════════════════════════════════════════════════╝
```

**Narration:**
> "Finally, the UHDC report generator creates a comprehensive HTML report combining all analyses. This single document contains the executive summary, technical details, economic comparisons, interactive maps, and the decision rationale. Stakeholders can explore the full analysis in one place."

**Visual:**
- Terminal showing report completion
- Open `output/ST010_HEINRICH_ZILLE_STRASSE/uhdc_report.html` in browser
- Scroll through: header, summary, maps, charts, decision section
- End on the final recommendation box

**Fallback:**
- **What could go wrong:** Template rendering error, missing assets
- **Recovery:** Use pre-generated report: `cp backup/ST010/uhdc_report.html output/ST010_HEINRICH_ZILLE_STRASSE/`
- **Alternative:** Show individual output files (maps, charts) separately

---

## Demo Checklist (Printable)

### Pre-Demo (10 min before)
- [ ] Environment activated
- [ ] Project directory verified
- [ ] Required packages installed
- [ ] Previous outputs cleaned (optional)
- [ ] Backup folder accessible
- [ ] Terminal font size 14+
- [ ] Browser ready
- [ ] VS Code open with relevant files

### During Demo
- [ ] Step 1: Data prep (30s) - Show street_cluster.html
- [ ] Step 2: CHA (1m) - Show interactive_map.html
- [ ] Step 3: DHA (1m) - Show hp_lv_map.html, highlight violations
- [ ] Step 4: Economics (30s) - Show LCOH values
- [ ] Step 5: Decision (1m) - Show decision box + LLM explanation
- [ ] Step 6: Report (30s) - Show uhdc_report.html

### Post-Demo
- [ ] Q&A ready
- [ ] Backup screenshots available if needed

---

## Timing Summary

| Step | Description | Duration | Cumulative |
|------|-------------|----------|------------|
| 1 | Data Preparation | 30s | 0:30 |
| 2 | CHA Simulation | 1:00 | 1:30 |
| 3 | DHA Analysis | 1:00 | 2:30 |
| 4 | Economics | 30s | 3:00 |
| 5 | Decision + LLM | 1:00 | 4:00 |
| 6 | Report Generation | 30s | 4:30 |
| -- | Buffer/Q&A | 30s | 5:00 |

**Total Target: 5 minutes**

---

## Fallback Summary Table

| Step | Risk | Fallback Action | Time Impact |
|------|------|-----------------|-------------|
| 1 | DB connection error | Use pre-generated data | None |
| 2 | Convergence failure | Use cached results | None |
| 3 | Power flow error | Use cached results | None |
| 4 | Long computation | Show cached results | -15s |
| 5 | LLM timeout | Show decision without LLM | -10s |
| 6 | Template error | Show pre-generated report | None |

---

## Quick Reference Commands

```bash
# Full pipeline (for pre-run)
python 00_prepare_data.py --street ST010_HEINRICH_ZILLE_STRASSE && \
python 01_run_cha.py --street ST010_HEINRICH_ZILLE_STRASSE --use-trunk-spur && \
python 02_run_dha.py --street ST010_HEINRICH_ZILLE_STRASSE --base-load-source bdew_timeseries && \
python 03_run_economics.py --street ST010_HEINRICH_ZILLE_STRASSE && \
python cli/decision.py --street ST010_HEINRICH_ZILLE_STRASSE --llm-explanation && \
python cli/uhdc.py --street ST010_HEINRICH_ZILLE_STRASSE

# Open all results
open output/ST010_HEINRICH_ZILLE_STRASSE/00_data/street_cluster.html
open output/ST010_HEINRICH_ZILLE_STRASSE/01_cha/interactive_map.html
open output/ST010_HEINRICH_ZILLE_STRASSE/02_dha/hp_lv_map.html
open output/ST010_HEINRICH_ZILLE_STRASSE/03_economics/lcoh_distribution.png
open output/ST010_HEINRICH_ZILLE_STRASSE/uhdc_report.html
```

---

## Key Talking Points (For Q&A)

1. **Why 94% confidence?** Monte Carlo with 10k iterations shows DH wins in 94% of scenarios.

2. **What about grid reinforcement?** Not included in HP costs - would make HP even more expensive.

3. **Trunk-spur optimization?** Optimizes pipe routing from central source to all buildings.

4. **BDEW load profiles?** Standard German load profiles for realistic heat demand modeling.

5. **LLM explanation value?** Makes technical results accessible to non-technical stakeholders.

6. **Scalability?** Pipeline can process entire cities; this is one street example.

---

*Demo script generated for Branitz2 Thesis Presentation*  
*Street: ST010_HEINRICH_ZILLE_STRASSE (23 buildings)*  
*Expected Decision: District Heating (94% confidence)*
