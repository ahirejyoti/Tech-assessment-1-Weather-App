
import os
import re
import math
from datetime import datetime, timezone
from collections import defaultdict

import requests
from flask import Flask, render_template, request, jsonify

# ---------- Config ----------
API_KEY = os.getenv("3f78723e682685fc3905204169eaceb8", "").strip()
if not API_KEY:
    print("[WARN]  is not set. Set it before running in production.")
BASE_WEATHER_URL = "https://api.openweathermap.org/data/2.5"
BASE_GEO_URL = "http://api.openweathermap.org/geo/1.0"

app = Flask(__name__)

# ---------- Utils ----------

def is_lat_lon(text: str):
    if not isinstance(text, str):
        return False
    m = re.match(r"^\s*([+-]?\d+(?:\.\d+)?)\s*,\s*([+-]?\d+(?:\.\d+)?)\s*$", text)
    if not m:
        return False
    lat = float(m.group(1))
    lon = float(m.group(2))
    return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0

def geocode(query: str, country_hint: str = "IN"):
    """
    Accepts: 
      - 'lat,lon' (returns as-is)
      - ZIP/Postal (numeric or alphanumeric) -> tries /geo/1.0/zip first
      - City/Town/Landmark -> /geo/1.0/direct
    """
    query = (query or "").strip()
    if not query:
        return None

    # If coordinates
    if is_lat_lon(query):
        lat, lon = [float(x) for x in query.split(",")]
        return {"name": "Your location", "lat": lat, "lon": lon}

    # Try ZIP (OpenWeather zip supports country; we'll try a couple of common codes)
    # Heuristic: if contains any digit and no comma and length <= 10, try as ZIP.
    if any(c.isdigit() for c in query) and ("," not in query) and len(query) <= 10:
        for country in [country_hint, "US", "GB", "CA", "AU"]:
            try:
                r = requests.get(f"{BASE_GEO_URL}/zip", params={
                    "zip": f"{query},{country}",
                    "appid": API_KEY
                }, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    return {
                        "name": f"{data.get('name','ZIP')} ({country})",
                        "lat": data["lat"],
                        "lon": data["lon"]
                    }
            except Exception:
                pass  # fall through

    # Fallback to direct geocoding for names/landmarks/cities
    r = requests.get(f"{BASE_GEO_URL}/direct", params={
        "q": query,
        "limit": 1,
        "appid": API_KEY
    }, timeout=10)
    if r.status_code != 200:
        return None
    arr = r.json()
    if not arr:
        return None
    top = arr[0]
    name_parts = [top.get("name")]
    if top.get("state"):
        name_parts.append(top["state"])
    if top.get("country"):
        name_parts.append(top["country"])
    return {
        "name": ", ".join([p for p in name_parts if p]),
        "lat": top["lat"],
        "lon": top["lon"]
    }

def fetch_current_and_forecast(lat: float, lon: float, units: str = "metric"):
    # Current
    cur = requests.get(f"{BASE_WEATHER_URL}/weather", params={
        "lat": lat,
        "lon": lon,
        "appid": API_KEY,
        "units": units
    }, timeout=10)
    cur.raise_for_status()
    current = cur.json()

    # Forecast (5 day / 3-hour)
    fc = requests.get(f"{BASE_WEATHER_URL}/forecast", params={
        "lat": lat,
        "lon": lon,
        "appid": API_KEY,
        "units": units
    }, timeout=10)
    fc.raise_for_status()
    forecast_raw = fc.json()

    # Aggregate into daily forecasts (next 5 days), pick around 12:00 local when possible
    by_date = defaultdict(list)
    for item in forecast_raw.get("list", []):
        dt_utc = datetime.utcfromtimestamp(item["dt"]).replace(tzinfo=timezone.utc)
        # Use city timezone offset if available
        tz_offset = forecast_raw.get("city", {}).get("timezone", 0)
        local_dt = dt_utc.timestamp() + tz_offset
        local_dt = datetime.fromtimestamp(local_dt)
        key = local_dt.date().isoformat()
        by_date[key].append((local_dt, item))

    daily = []
    for date_key, items in sorted(by_date.items())[:5]:
        # choose item closest to 12:00
        target_hour = 12
        chosen = min(items, key=lambda x: abs(x[0].hour - target_hour))
        _, best = chosen
        temps = [it[1]["main"]["temp"] for it in items]
        tmin = min(temps)
        tmax = max(temps)
        weather = best["weather"][0]
        daily.append({
            "date": date_key,
            "temp_min": round(tmin, 1),
            "temp_max": round(tmax, 1),
            "description": weather["description"].title(),
            "icon": weather["icon"]
        })

    return current, daily

# ---------- Routes ----------

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/weather")
def api_weather():
    if not API_KEY:
        return jsonify({"error": "Server is missing OPENWEATHER_API_KEY"}), 500

    query = request.args.get("query", "").strip()
    lat = request.args.get("lat", "").strip()
    lon = request.args.get("lon", "").strip()
    units = request.args.get("units", "metric")

    # If lat/lon provided, use directly
    loc = None
    if lat and lon:
        try:
            loc = {
                "name": "Your location",
                "lat": float(lat),
                "lon": float(lon),
            }
        except ValueError:
            pass

    # Otherwise geocode the query
    if loc is None:
        loc = geocode(query)

    if not loc:
        return jsonify({"error": "Location not found. Try a city name, landmark, ZIP, or 'lat,lon'."}), 404

    try:
        current, forecast = fetch_current_and_forecast(loc["lat"], loc["lon"], units=units)
    except requests.HTTPError as e:
        return jsonify({"error": f"Weather API error: {e.response.status_code} {e.response.text}"}), 502
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500

    # Prepare response
    cur_weather = current["weather"][0]
    out = {
        "location_name": loc["name"],
        "units": units,
        "current": {
            "temp": round(current["main"]["temp"], 1),
            "feels_like": round(current["main"]["feels_like"], 1),
            "humidity": current["main"]["humidity"],
            "pressure": current["main"]["pressure"],
            "wind_speed": round(current["wind"]["speed"], 1),
            "description": cur_weather["description"].title(),
            "icon": cur_weather["icon"]
        },
        "forecast": forecast
    }
    return jsonify(out)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
