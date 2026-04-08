import os
import sys
import yaml
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.google_sheets import DoreAndRoseSheets


def load_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    with open(config_path) as f:
        return yaml.safe_load(f)


def create_app():
    config = load_config()
    frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

    app = Flask(__name__, static_folder=frontend_dir, static_url_path="")
    CORS(app)

    sheets = DoreAndRoseSheets(config)

    @app.route("/")
    def index():
        return send_from_directory(frontend_dir, "index.html")

    @app.route("/api/dashboard")
    def dashboard():
        try:
            data = sheets.get_dashboard_data()
            return jsonify({"status": "ok", "data": data})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/month/<path:tab_name>")
    def month_detail(tab_name):
        try:
            data = sheets.get_month_detail(tab_name)
            return jsonify({"status": "ok", "data": data})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/targets")
    def targets():
        try:
            target_config = config.get("targets", {})
            categories = target_config.get("categories", {})
            target_year = target_config.get("year", 2026)

            actuals = sheets.get_category_actuals(target_config)

            result = {}
            for cat_name, cat_conf in categories.items():
                quarterly_targets = cat_conf.get("quarterly", [0, 0, 0, 0])
                monthly = actuals.get(cat_name, {})

                quarterly_actuals = [0.0, 0.0, 0.0, 0.0]
                for month_key, rev in monthly.items():
                    month_num = int(month_key.split("-")[1])
                    q = (month_num - 1) // 3
                    if 0 <= q < 4:
                        quarterly_actuals[q] += rev

                ytd_actual = sum(quarterly_actuals)
                ytd_target = sum(quarterly_targets)

                result[cat_name] = {
                    "quarterly_targets": quarterly_targets,
                    "quarterly_actuals": [round(v, 0) for v in quarterly_actuals],
                    "monthly": monthly,
                    "ytd_actual": round(ytd_actual, 0),
                    "ytd_target": ytd_target,
                    "ytd_pct": round((ytd_actual / ytd_target * 100) if ytd_target else 0, 1),
                }

            total_q_targets = [0, 0, 0, 0]
            total_q_actuals = [0.0, 0.0, 0.0, 0.0]
            for cat in result.values():
                for i in range(4):
                    total_q_targets[i] += cat["quarterly_targets"][i]
                    total_q_actuals[i] += cat["quarterly_actuals"][i]

            total_ytd_actual = sum(total_q_actuals)
            total_ytd_target = sum(total_q_targets)
            result["Total GMV"] = {
                "quarterly_targets": total_q_targets,
                "quarterly_actuals": [round(v, 0) for v in total_q_actuals],
                "ytd_actual": round(total_ytd_actual, 0),
                "ytd_target": total_ytd_target,
                "ytd_pct": round((total_ytd_actual / total_ytd_target * 100) if total_ytd_target else 0, 1),
            }

            return jsonify({"status": "ok", "data": {"year": target_year, "categories": result}})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/refresh")
    def refresh():
        try:
            data = sheets.get_dashboard_data(force_refresh=True)
            return jsonify({"status": "ok", "data": data})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    return app


# Module-level app for gunicorn
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5070))
    print(f"Dore & Rose Dashboard running on http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
