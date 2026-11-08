"""Our picture for a game whose animation did not work out: a road through
hills at sunset (one still frame - the tile and the scene in AP). Uses the
same contract as the AI code (rysownik/klatki.py)."""

SKY = ["#2B2D5C", "#5B3F7A", "#B5577A", "#F08A5D", "#F9C46B"]
SUN = "#FFE7A3"
HILLS = ["#6C5A8E", "#4D4677", "#2F3A5E"]
ROAD = "#D9B98C"
TREE = "#1E2A3F"


def rysuj(d, t, w, h):
    d.rectangle([0, 0, w, h], fill=SKY[-1])  # under the hills too - no white gaps
    band = h * 0.62 / len(SKY)
    for i, colour in enumerate(SKY):
        d.rectangle([0, i * band, w, (i + 1) * band + 2], fill=colour)
    r = w * 0.12
    d.ellipse([w * 0.5 - r, h * 0.62 - r, w * 0.5 + r, h * 0.62 + r], fill=SUN)
    for i, colour in enumerate(HILLS):
        top = h * (0.55 + 0.1 * i)
        points = [(0, h)]
        for k in range(9):
            x = w * k / 8
            points.append((x, top + h * 0.05 * ((k + i) % 3)))
        points.append((w, h))
        d.polygon(points, fill=colour)
    d.polygon([(w * 0.47, h * 0.72), (w * 0.53, h * 0.72), (w * 0.75, h), (w * 0.25, h)], fill=ROAD)
    for x, size in ((0.15, 1.0), (0.85, 0.8), (0.72, 0.55)):
        cx, base, s = w * x, h * (0.92 - 0.12 * (1 - size)), h * 0.18 * size
        d.rectangle([cx - s * 0.06, base - s * 0.35, cx + s * 0.06, base], fill=TREE)
        d.polygon([(cx - s * 0.35, base - s * 0.3), (cx + s * 0.35, base - s * 0.3), (cx, base - s * 1.2)],
                  fill=TREE)
