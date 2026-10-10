# Screenshots

Drop the dashboard PNGs here (referenced from the main `README.md`):

| File | View |
|------|------|
| `01-dashboard.png` | Dashboard + 500 m AQI grid, colour-coded, guided 4-step strip |
| `02-forecast-slider.png` | Forecast time-slider (scrub the next 6 h on the map) |
| `03-route-compare.png` | Cleanest vs fastest route with clean-index scores |
| `04-school-agent.png` | School decision card (Cedar verdict + indoor advisory) + agent reply |

## How to capture

```bash
python run.py          # open http://localhost:8000
```

1. **Dashboard** - the landing view, after clicking "Run 15-min cycle".
2. **Forecast slider** - drag the time-slider to a later hour; the map recolours.
3. **Route compare** - click "Compare routes", or use "Pick on map" / "Near me".
4. **School + agent** - pick a school, and ask the agent a question (e.g. "Should ABC
   School hold outdoor assembly at 8am tomorrow?").

Keep each image under ~300 KB (a full-window browser screenshot at 1280 px is fine).
Then uncomment the image block in the main `README.md` to embed them.
