# Branitz2 Demo - Presenter Quick Reference Card
## Print this and keep handy during presentation

---

## Expected Results (Memorize These!)

| Metric | Value | Status |
|--------|-------|--------|
| Buildings | 23 | - |
| DH LCOH | 92.6 €/MWh | ✓ Winner |
| HP LCOH | 124.5 €/MWh | ✗ Loser |
| Cost Difference | 31.9 €/MWh | DH cheaper |
| HP Violations | 116 | Critical |
| DH Confidence | 94% | Robust |
| Decision | DH | Recommended |

---

## Command Cheat Sheet

```bash
# Step 1 (30s)
python 00_prepare_data.py --street ST010_HEINRICH_ZILLE_STRASSE

# Step 2 (1m)
python 01_run_cha.py --street ST010_HEINRICH_ZILLE_STRASSE --use-trunk-spur

# Step 3 (1m)
python 02_run_dha.py --street ST010_HEINRICH_ZILLE_STRASSE --base-load-source bdew_timeseries

# Step 4 (30s)
python 03_run_economics.py --street ST010_HEINRICH_ZILLE_STRASSE

# Step 5 (1m)
python cli/decision.py --street ST010_HEINRICH_ZILLE_STRASSE --llm-explanation

# Step 6 (30s)
python cli/uhdc.py --street ST010_HEINRICH_ZILLE_STRASSE
```

---

## File Paths to Open

| Step | File Path |
|------|-----------|
| 1 | `output/ST010_HEINRICH_ZILLE_STRASSE/00_data/street_cluster.html` |
| 2 | `output/ST010_HEINRICH_ZILLE_STRASSE/01_cha/interactive_map.html` |
| 3 | `output/ST010_HEINRICH_ZILLE_STRASSE/02_dha/hp_lv_map.html` |
| 4 | `output/ST010_HEINRICH_ZILLE_STRASSE/03_economics/lcoh_distribution.png` |
| 6 | `output/ST010_HEINRICH_ZILLE_STRASSE/uhdc_report.html` |

---

## Narration Keywords (Don't Forget!)

- **Step 1:** "23 buildings", "1.8 megawatts", "foundation"
- **Step 2:** "pandapipes", "trunk-spur", "850 meters", "4.2% losses"
- **Step 3:** "pandapower", "116 violations", "voltage drops", "line overloads"
- **Step 4:** "Monte Carlo", "10,000 iterations", "30 euros cheaper"
- **Step 5:** "94% confidence", "robust decision", "LLM explanation"
- **Step 6:** "comprehensive report", "stakeholders"

---

## Emergency Fallbacks

| If This Happens | Do This |
|-----------------|---------|
| Command hangs | Ctrl+C, use backup files |
| Error message | Say "Let me show the pre-computed results" |
| Browser won't open | Show VS Code preview or terminal output |
| Demo runs long | Skip to Step 5 (Decision) directly |
| Total failure | Show backup screenshots folder |

---

## Q&A Prep

**Q: Why not heat pumps?**
A: 116 grid violations + 30€/MWh more expensive

**Q: What about grid reinforcement?**
A: Not included - would make HP even more expensive

**Q: How confident is the decision?**
A: 94% - robust across 10k Monte Carlo scenarios

**Q: Can this scale to city-level?**
A: Yes, pipeline processes entire cities

**Q: What about renewable energy?**
A: DH can use waste heat; HP depends on grid mix

---

## Timing Watch Points

- [ ] 0:30 - Step 1 complete
- [ ] 1:30 - Step 2 complete
- [ ] 2:30 - Step 3 complete (highlight violations!)
- [ ] 3:00 - Step 4 complete
- [ ] 4:00 - Step 5 complete (read LLM text!)
- [ ] 4:30 - Step 6 complete
- [ ] 5:00 - Finish, Q&A ready

---

## Backup Files Location
```
backup/ST010/
├── 00_data/
├── 01_cha/
├── 02_dha/
├── 03_economics/
└── uhdc_report.html
```

---

## One-Line Summary
> "For Heinrich-Zille-Straße, District Heating wins with 94% confidence - it's 30€/MWh cheaper and the grid can't handle 23 heat pumps."

---

*Print this card and keep it visible during your presentation*
