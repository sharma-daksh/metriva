# Metriva — Payment Intelligence & Revenue Recovery
## Architecture

```
metriva/
    backend/
        app/
            main.py              # FastAPI entrypoint, mounts routers
            config.py             # settings (CORS origins, paths, DB URL)
            api/routes/
                merchants.py      # /api/merchants, /api/merchants/{id}, .../daily-metrics
                incidents.py      # /api/incidents, /api/incidents/{id}, /api/incidents/summary
            services/
                data_generation.py     # Phase 2: synthetic raw UPI dataset
                ingestion.py            # Phase 2: structural CSV validation
                normalization.py        # Phase 3/5: canonical mapping + data quality
                metrics.py               # Phase 6: daily/merchant/dimension metrics
                baseline.py               # Phase 7: historical baseline (rolling/pooled/insufficient)
                anomaly_detection.py      # Phase 8: volume-aware binomial-test detector
                incident_engine.py        # Phase 9: groups anomalies into incidents
                incident_simulation.py    # Phase 10: injects 6 ground-truth scenarios
                pipeline.py                # runs raw -> canonical -> processed
            storage/repositories.py    # CSV-backed data access for the API
        scripts/
            inject_incidents.py     # builds incident_transactions.csv + ground_truth_incidents.csv
            compute_incidents.py    # recomputes daily/merchant metrics + incidents.csv from the injected data
        data/
            raw/         # immutable synthetic source data
            processed/   # pipeline + detection outputs (see below)
    frontend/
        src/
            pages/
                OverviewPage.jsx       # merchant selector, KPIs, health chart, active alerts
                IncidentsPage.jsx       # filterable incident table
                IncidentDetailPage.jsx  # timeline, revenue-at-risk breakdown
            components/
                AppLayout.jsx    # top nav shell
                Cards.jsx         # KPI cards, severity/status badges
            services/api.js     # all backend calls
```

Backend: FastAPI + pandas/scipy. Frontend: React + Vite + Recharts. No
database yet — the API reads precomputed CSVs directly (fine at this data
scale; a real DB layer is Phase 45).

## Running it — full pipeline, in order

**1. Backend: build the data (first time, or after changing generation logic)**
```bash
cd backend
pip install -r requirements.txt --break-system-packages
python -m app.services.pipeline        
python -m scripts.inject_incidents     
python -m scripts.compute_incidents    
```


**2. Backend: start the API**
```bash
uvicorn app.main:app --reload --port 8000
```
Verify: `curl http://localhost:8000/api/incidents/summary` should return a
JSON object with `total_revenue_at_risk_low`, `open_incidents`, etc.

**3. Frontend**
```bash
cd frontend
npm install
npm run dev
```
