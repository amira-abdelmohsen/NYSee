# NYSee MVP

A beginner-friendly hackathon MVP for visually impaired NYC pedestrians.

## What this version does

- **Image analysis button**: send one photo to Google Cloud Vision and read back labels + visible text.
- **Find nearest APS button**: use the browser's location API and look up the nearest Accessible Pedestrian Signal (APS) in NYC Open Data.
- **Replay / stop audio**: speak the latest result with the browser's built-in text-to-speech.

This version keeps image analysis and location lookup as **separate buttons**, which makes the UI simpler and the code easier to demo.

## Directory layout

```text
nysee_mvp/
  README.md
  backend/
    .env.example
    requirements.txt
    app/
      __init__.py
      main.py
      services/
        __init__.py
        nyc_open_data.py
        vision.py
  frontend/
    index.html
    styles.css
    app.js
```

## Backend setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Set `GOOGLE_APPLICATION_CREDENTIALS` in `.env` to the path of your Google Cloud service account JSON.

Then run:

```bash
uvicorn app.main:app --reload
```

The API will run at `http://127.0.0.1:8000`.

## Frontend setup

Because the browser camera and geolocation APIs work best from a local server, serve the `frontend/` folder instead of opening `index.html` directly.

Example:

```bash
cd frontend
python -m http.server 5500
```

Then open:

```text
http://127.0.0.1:5500
```

## Notes

- The frontend expects the backend at `http://127.0.0.1:8000/api`.
- If the APS dataset uses slightly different field names in a live response, adjust `_best_name()` and `_extract_coords()` in `backend/app/services/nyc_open_data.py`.
- For the hackathon, test image mode and location mode independently before polishing UI.
