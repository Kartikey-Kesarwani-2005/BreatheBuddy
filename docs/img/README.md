# Screenshots

These PNGs are captured from the running dashboard and are embedded in the main
`README.md`:

| File | View |
|------|------|
| `01-dashboard.png` | Dashboard + 500 m AQI grid, colour-coded, guided 4-step strip |
| `02-forecast-slider.png` | Forecast time-slider (scrub the next 6 h on the map) |
| `03-route-compare.png` | Cleanest vs fastest route with clean-index scores |
| `04-school-agent.png` | School decision card (Cedar verdict + indoor advisory) + agent reply |

## How to refresh them

```bash
python run.py          # open http://localhost:8000
```

1. **Dashboard** - the landing view, after clicking "Run 15-min cycle".
2. **Forecast slider** - drag the time-slider to a later hour; the map recolours.
3. **Route compare** - click "Compare routes", or use "Pick on map" / "Near me".
4. **School + agent** - pick a school, and ask the agent a question (e.g. "Should ABC
   School hold outdoor assembly at 8am tomorrow?").

Capture each view at ~1400x900 and overwrite the matching file above. Keep each
image under ~1.3 MB (a full-window browser screenshot is fine).
