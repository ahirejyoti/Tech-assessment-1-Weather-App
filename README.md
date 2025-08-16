
# Python Flask Weather App

A minimal weather app that shows **current weather** and a **5‑day forecast** using OpenWeather.
It supports:
- Free‑text location (city/town/landmark), ZIP/postal code, and raw coordinates (`lat,lon`).
- **Use My Location** via the browser Geolocation API.
- Metric/Imperial units toggle.
- Weather icons and simple, clean UI.

## Quick Start

1. **Get an API key** from https://openweathermap.org/ (free tier works).
2. **Set the env var** (Windows PowerShell example):
   ```powershell
   $env:OPENWEATHER_API_KEY="YOUR_API_KEY"
   ```
   macOS/Linux (bash/zsh):
   ```bash
   export OPENWEATHER_API_KEY="YOUR_API_KEY"
   ```
3. **Install dependencies & run**:
   ```bash
   pip install -r requirements.txt
   python app.py
   ```
4. Open: http://localhost:5000

## Notes

- ZIP lookups try your local country first (`IN` by default), then fall back to `US`, `GB`, `CA`, `AU`.
- 5‑day forecast is aggregated from OpenWeather's **3‑hourly** data: we compute each day's min/max and pick the slot closest to **12:00** local time for icon/description.
- If you prefer Fahrenheit/mph: switch **Imperial** from the dropdown.

## Project Structure

```
python-flask-weather-app/
├── app.py
├── requirements.txt
├── templates/
│   └── index.html
└── static/
    ├── styles.css
    └── script.js
```

## Production Tips (Nice to have)
- Add simple response caching to avoid hitting API limits (e.g., `functools.lru_cache` or a small TTL in Redis).
- Add automated tests for geocoding heuristics and forecast aggregation.
- Serve behind a real web server (gunicorn/uvicorn + reverse proxy).
- Store the API key as a secret in your deployment platform.
