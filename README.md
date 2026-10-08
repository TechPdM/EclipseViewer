# EclipseViewer

Can you see the partial solar eclipse of **12 August 2026** from Bristol, or does the horizon get in the way?

The eclipse happens in the evening with the sun low in the west-north-west, so the answer depends on the skyline. This project models that skyline from elevation data for two viewing spots and compares it with the sun's path.

| Site | Page | Verdict |
| --- | --- | --- |
| Troopers Hill (summit, 71 m) | `troopers-hill-eclipse.html` | Clear. The skyline never rises above 0.35°, leaving +3.7° of clearance at the end of the eclipse. |
| Oldbury Court (Frome valley, 51 m) | `oldbury-court-eclipse.html` | Clear, but tighter. A ridge 1.5–2.6 km west sits 0.8–1.4° up, leaving +2.9° at the end. |

Eclipse times for Bristol (BST): begins 18:17, maximum 19:13 (94% magnitude), ends 20:07.

## Viewing

Open either HTML file in a browser. Each page is self-contained, with:

- a verdict and the key numbers
- an interactive 3D terrain model with the sun's track, viewable from the observer's eye or from orbit
- a chart of sun altitude against the terrain horizon
- a table of contact times and clearances

Nothing needs to be built or served. The only external dependency is three.js, loaded from a CDN.

## How it works

- **Terrain:** EU-DEM v1.1 elevation data (25 m resolution). 39 sightlines fan out from the observer between bearings 248° and 305°, sampled out to 60 km. The highest angle along each sightline is the horizon on that bearing.
- **Horizon angle:** corrected for Earth curvature and standard atmospheric refraction, from an eye height of 1.6 m.
- **Sun position:** the NOAA solar position algorithm, cross-checked against timeanddate.com to within 0.1°.

The model is bare earth, with no trees or buildings, so the real skyline is higher wherever those stand on it.

## Layout

```
troopers-hill-eclipse.html    Finished page, Troopers Hill
oldbury-court-eclipse.html    Finished page, Oldbury Court
eclipse/                      Analysis and page source, Troopers Hill
eclipse-oc/                   Analysis and page source, Oldbury Court
deploy/                       Netlify-ready copy of the Troopers Hill page
```

In each analysis folder, `sun.py` computes the sun's position, `analyse.py` compares it with the horizon profile and writes `analysis.json`, and `template.html` is the page that the results and terrain grids are embedded in.

## Re-running the analysis

Requires Python 3, standard library only.

```sh
cd eclipse        # or eclipse-oc
python3 analyse.py
```

This prints the clearance at each contact and rewrites `analysis.json`.

## Deploying

`deploy/` is ready to drop onto Netlify. See `deploy/README.md`.

## Safety

Never look at the sun without certified eclipse glasses (ISO 12312-2) or a proper solar filter, even at 94% coverage.
