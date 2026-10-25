"""Line-delimited test transport for the real frontend client and FastAPI app.

This replaces only the TCP transport. Requests still traverse TestClient,
FastAPI validation, SQLite, the worker, numerical engine and Droid toolbox.
It does not install test routes in the product or substitute API responses.
"""
from datetime import datetime, timezone
import json
import sys
from tempfile import TemporaryDirectory
import traceback

from fastapi.testclient import TestClient
from app.core.clock import FrozenClock, SequentialIdFactory
from app.forecasting.demo import create_demo_app, import_observed_actuals, observed_inputs
from app.forecasting.fixtures import northstar_evidence
from app.seed.northstar import seed


def main():
    clock = FrozenClock(datetime(2026, 10, 26, tzinfo=timezone.utc))
    with TemporaryDirectory(prefix="forecast-frontend-") as directory:
        app = create_demo_app(directory, clock)
        app.state.id_factory = SequentialIdFactory()
        with app.state.session_factory() as session:
            seed(session, clock=clock, ids=app.state.id_factory, include_spend=False)
        import_observed_actuals(app, observed_inputs(now=clock.now().isoformat()), clock)
        with TestClient(app) as client:
            for line in sys.stdin:
                message = json.loads(line)
                try:
                    if message["operation"] == "request":
                        response = client.request(message.get("method", "GET"), message["path"],
                                                  headers=message.get("headers"), content=message.get("body"))
                        result = {"status": response.status_code, "body": response.text,
                                  "headers": dict(response.headers)}
                    elif message["operation"] == "work":
                        result = app.state.forecast_worker.process_one(job_id=message.get("job_id"))
                    elif message["operation"] == "events":
                        result = northstar_evidence()
                    elif message["operation"] == "advance":
                        clock.advance(days=message["days"])
                        import_observed_actuals(app, observed_inputs(now=clock.now().isoformat()), clock)
                        result = clock.now().isoformat()
                    else:
                        raise ValueError("Unknown test transport operation")
                    output = {"id": message["id"], "result": result}
                except Exception:
                    output = {"id": message["id"], "error": traceback.format_exc()}
                print(json.dumps(output, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
