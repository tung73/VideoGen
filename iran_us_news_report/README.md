# Iran–U.S. Conflict News Report (Female Anchor)

Broadcast-style situation briefing as of **27 July 2026**, with a female studio anchor and 3D situation graphics.

## Outputs

- `output/Iran_US_War_News_Report_Anchor_iPhone.mp4` — Safari/iPhone faststart encode
- Published at `docs/Iran_US_War_News_Report_Anchor.mp4`

## Generate

```bash
# Requires prior 3D frames from generate_report.py (map3d + timeline3d)
python3 iran_us_news_report/generate_anchor_report.py
```

## Performance design

- Anchor: dark navy blazer, upright desk posture, blue world-map LED newsroom
- Opening smile → speaking blink/nod → palm-turn gestures on emphasis
- Female neural TTS: `en-US-AvaNeural`
- A-roll studio ↔ B-roll 3D Hormuz map / conflict timeline
