# Run the ResoScan backend (from the backend/ directory).
# Uses the same Python 3.10 interpreter that has scipy/sklearn for the engine.
python -m uvicorn app.main:app --reload --port 8000
