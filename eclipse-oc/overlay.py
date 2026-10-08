"""Draw the model's sun track and terrain skyline over photos taken on the day.

The camera's direction is not recorded, so each photo is oriented by pinning the
sun's image to its computed altitude/azimuth at the EXIF timestamp. Everything
else drawn (altitude lines, sun track, terrain skyline) follows from that.

Pinning makes the sun line up by construction, so the independent check is between
photos: the 18:40:29 shot is the reference, and the tree line it records is used to
orient the other shots. Where the model then puts the sun is compared with the glare.
"""
import json, math, os, sys
from datetime import datetime, timedelta
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ExifTags
from sun import sun_altaz, BST

HERE = os.path.dirname(os.path.abspath(__file__))
PHOTOS = os.path.join(HERE, '..', 'photos')
OUT = os.path.join(PHOTOS, 'overlays')
# roll = camera tilt in degrees (clockwise positive), judged from the far edge of the field
# moved = taken from a different spot to the reference photo, so nearby trees shift sideways
SHOTS = [('PXL_20260812_174004617.jpg', 'oldbury-court-1840a', 0.0, False),
         ('13b15408-4078-4d34-a309-7ae669ac0c85-1_all_39226.jpg', 'oldbury-court-1840b', 0.0, False),
         ('13b15408-4078-4d34-a309-7ae669ac0c85-1_all_39227.jpg', 'oldbury-court-1900', 0.0, True)]

DATA = json.load(open(os.path.join(HERE, 'analysis.json')))
HOR = DATA['hor']
C1 = datetime(2026,8,12,18,17,6,tzinfo=BST)
MX = datetime(2026,8,12,19,13,45,tzinfo=BST)
C4 = datetime(2026,8,12,20,7,18,tzinfo=BST)
D2R = math.pi/180
FONT = '/System/Library/Fonts/Helvetica.ttc'
REF = 'oldbury-court-1840b'

class Camera:
    """Pinhole camera, principal point at the image centre, oriented by yaw/pitch/roll."""
    def __init__(self, w, h, f35, roll):
        self.w, self.h = w, h
        self.F = f35/43.267 * math.hypot(w, h)      # focal length in pixels
        self.roll = roll*D2R; self.yaw = self.pitch = 0.0

    def _unroll(self, px, py):
        X, Y = (px - self.w/2)/self.F, (self.h/2 - py)/self.F
        c, s = math.cos(self.roll), math.sin(self.roll)
        return X*c - Y*s, X*s + Y*c

    def pin(self, px, py, alt, az):
        """Solve yaw and pitch so pixel (px,py) looks at (alt,az)."""
        X, Y = self._unroll(px, py)
        n = math.sqrt(X*X + Y*Y + 1)
        self.pitch = math.asin(n*math.sin(alt*D2R)/math.hypot(Y, 1)) - math.atan2(Y, 1)
        fwd = math.cos(self.pitch) - Y*math.sin(self.pitch)
        self.yaw = az*D2R - math.atan2(X, fwd)

    def project(self, alt, az):
        a, d = alt*D2R, az*D2R - self.yaw
        e, n, u = math.cos(a)*math.sin(d), math.cos(a)*math.cos(d), math.sin(a)
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        Z = n*cp + u*sp
        if Z <= 0.05: return None
        X, Y = e/Z, (u*cp - n*sp)/Z
        c, s = math.cos(self.roll), math.sin(self.roll)
        X, Y = X*c + Y*s, -X*s + Y*c
        return self.w/2 + X*self.F, self.h/2 - Y*self.F

    def unproject(self, px, py):
        X, Y = self._unroll(px, py)
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        n, u = cp - Y*sp, Y*cp + sp
        return (math.atan2(u, math.hypot(X, n))/D2R,
                ((self.yaw + math.atan2(X, n))/D2R) % 360)

def exif_time(im):
    ex = im.getexif().get_ifd(ExifTags.IFD.Exif)
    t = datetime.strptime(ex[36867], '%Y:%m:%d %H:%M:%S')      # DateTimeOriginal, local (BST)
    return t.replace(tzinfo=BST), ex.get(41989, 24)            # FocalLengthIn35mmFilm

def find_sun(lum):
    """Centre of the sun's glare: centroid of the saturated blob around the brightest area."""
    k = 16
    small = lum[:lum.shape[0]//k*k, :lum.shape[1]//k*k].reshape(lum.shape[0]//k, k, lum.shape[1]//k, k).mean((1,3))
    pad = np.pad(small, 4, mode='edge')
    blur = sum(pad[i:i+small.shape[0], j:j+small.shape[1]] for i in range(9) for j in range(9))
    cy, cx = np.unravel_index(blur.argmax(), blur.shape)
    cy, cx, r = cy*k + k//2, cx*k + k//2, 260
    y0, x0 = max(0, cy-r), max(0, cx-r)
    win = lum[y0:cy+r, x0:cx+r]
    ys, xs = np.nonzero(win >= win.max() - 2)
    return x0 + xs.mean(), y0 + ys.mean()

def otsu(v):
    hist = np.bincount(v.astype(np.uint8).ravel(), minlength=256).astype(float)
    tot, s_all = hist.sum(), (hist*np.arange(256)).sum()
    best, thr, w0, s0 = -1, 0, 0.0, 0.0
    for t in range(256):
        w0 += hist[t]; s0 += t*hist[t]
        if w0 == 0 or w0 == tot: continue
        var = w0*(tot-w0)*((s0/w0) - (s_all-s0)/(tot-w0))**2
        if var > best: best, thr = var, t
    return thr

def tree_line(lum):
    """For each column, the first row (from the top) where sky gives way to something dark."""
    h, w = lum.shape
    top = lum[:int(h*0.6)]
    thr = otsu(top)
    while (lum[:20] < thr).mean() > 0.2:        # dim sky at the top counted as dark: split again
        thr = otsu(top[top < thr])
    dark = lum < thr
    run = 40                                    # must stay dark for this many rows
    cs = np.cumsum(np.vstack([np.zeros((1, w)), dark]), axis=0)
    solid = (cs[run:] - cs[:-run]) >= run*0.9
    first = solid.argmax(axis=0).astype(float)
    first[~solid.any(axis=0)] = np.nan
    return first

def hor_at(az):
    for a, b in zip(HOR, HOR[1:]):
        if a['az'] <= az <= b['az']:
            return a['alt'] + (az-a['az'])/(b['az']-a['az'])*(b['alt']-a['alt'])

def prepare(fname, roll):
    """Orient a photo on its own sun and measure its tree line as (azimuth, altitude)."""
    im = Image.open(os.path.join(PHOTOS, fname)).convert('RGB')
    t0, f35 = exif_time(Image.open(os.path.join(PHOTOS, fname)))
    w, h = im.size
    lum = np.asarray(im.convert('L')).astype(float)
    sx, sy = find_sun(lum)
    alt0, az0, _ = sun_altaz(t0)
    cam = Camera(w, h, f35, roll); cam.pin(sx, sy, alt0, az0)
    trees = tree_line(lum)
    pts = sorted((cam.unproject(x, trees[x])[::-1] for x in range(0, w, 4) if not np.isnan(trees[x])))
    prof = (np.array([p[0] for p in pts]), np.array([p[1] for p in pts]))
    return dict(im=im, t0=t0, sun=(sx, sy), alt0=alt0, az0=az0, cam=cam, trees=trees, prof=prof)

def align(prof, ref, lo=280, hi=303):
    """Shift (d_az, d_alt) that best lays this photo's tree line over the reference one.
    The range stays right of the sun, clear of the flare."""
    g = np.arange(lo, hi, 0.05); r = np.interp(g, *ref); best = None
    for daz in np.arange(-4, 4.01, 0.05):
        c = np.interp(g, prof[0] + daz, prof[1], left=np.nan, right=np.nan); ok = ~np.isnan(c)
        if ok.sum() < len(g)*0.7: continue
        d = r[ok] - c[ok]; dalt = np.median(d); score = np.mean(np.abs(d - dalt))
        if best is None or score < best[0]: best = (score, daz, dalt)
    return best

def run(outname, shot, check, moved):
    im, t0, (sx, sy), alt0, az0, cam, trees = (shot[k] for k in ('im','t0','sun','alt0','az0','cam','trees'))
    w, h = im.size

    # where the sun's centre first meets the photographed tree line
    met, t = None, t0
    while t <= datetime(2026,8,12,20,45,tzinfo=BST):
        a, z, _ = sun_altaz(t); p = cam.project(a, z)
        if p and 0 <= p[0] < w and not np.isnan(trees[int(p[0])]) and p[1] >= trees[int(p[0])]:
            met = (t, a, z, p); break
        t += timedelta(seconds=15)

    d = ImageDraw.Draw(im, 'RGBA')
    f_s, f_m, f_l = (ImageFont.truetype(FONT, s) for s in (44, 54, 66))
    def text(xy, s, font, fill, anchor='la'):
        d.text(xy, s, font=font, fill=fill, anchor=anchor, stroke_width=5, stroke_fill=(0,0,0,210))
    def polyline(pts, fill, width, dash=None):
        seg = [p for p in pts if p]
        for i in range(len(seg)-1):
            if dash and (i // dash) % 2: continue
            d.line([seg[i], seg[i+1]], fill=fill, width=width)

    left, right = cam.unproject(0, h*0.45)[1], cam.unproject(w, h*0.45)[1]
    azs = np.arange(left-3, right+3, 0.25)
    for alt in (0, 5, 10, 15, 20):                              # altitude lines
        pts = [cam.project(alt, z) for z in azs]
        polyline(pts, (255,255,255,150 if alt == 0 else 80), 5 if alt == 0 else 3, dash=None if alt == 0 else 3)
        p = cam.project(alt, cam.unproject(30, h*0.45)[1])
        if p: text((30, p[1]-8), f'{alt}°' + (' eye level' if alt == 0 else ''), f_s, (255,255,255,230), 'ls')
    polyline([cam.project(hor_at(z), z) for z in azs if hor_at(z) is not None], (248,81,73,255), 6)  # model terrain

    track, t = [], datetime(2026,8,12,18,0,tzinfo=BST)          # sun track
    while t <= datetime(2026,8,12,20,45,tzinfo=BST):
        a, z, _ = sun_altaz(t); track.append((t, cam.project(a, z))); t += timedelta(minutes=1)
    polyline([p for t, p in track if not C1 <= t <= C4], (255,184,77,170), 5)
    polyline([p for t, p in track if C1 <= t <= C4], (255,140,50,255), 9)
    for t, p in track:
        near = min(abs((t-e).total_seconds()) for e in [t0, MX, C4] + ([met[0]] if met else []))
        if p and t.minute % 10 == 0 and 0 < p[0] < w and 0 < p[1] < h and near > 360:
            d.ellipse([p[0]-11, p[1]-11, p[0]+11, p[1]+11], fill=(255,184,77,255))
            text((p[0]+24, p[1]), t.strftime('%H:%M'), f_s, (255,214,150,255), 'lm')
    for lab, tt in (('max 19:13', MX), ('eclipse ends 20:07', C4)):
        a, z, _ = sun_altaz(tt); p = cam.project(a, z)
        if p and 0 < p[0] < w and 0 < p[1] < h:
            d.ellipse([p[0]-26, p[1]-26, p[0]+26, p[1]+26], outline=(255,255,255,255), width=6)
            text((p[0]-40, p[1]+(30 if tt == C4 else 0)), lab, f_m, (255,255,255,255), 'rm')
    d.ellipse([sx-60, sy-60, sx+60, sy+60], outline=(255,255,255,255), width=6)
    if check:                                                   # sun as predicted from the reference photo's trees
        _, daz, dalt = check
        px, py = cam.project(alt0 - dalt, az0 - daz)
        for dx, dy in ((1,0),(0,1)):
            d.line([px-dx*95, py-dy*95, px+dx*95, py+dy*95], fill=(90,220,255,255), width=7)
        text((sx+85, sy+45), f'cyan cross: sun predicted via the 18:40:29 trees\noff by {abs(daz):.1f}° sideways' +
             (' (camera had moved a few metres)' if moved else '') + f', {abs(dalt):.1f}° in height',
             f_s, (150,235,255,255), 'la')
    else:
        text((sx+85, sy+45), 'reference photo: the others are\nchecked against this tree line', f_s, (150,235,255,255), 'la')
    text((sx+85, sy), f'sun at {t0:%H:%M:%S} · {alt0:.1f}° up · bearing {az0:.1f}°', f_m, (255,255,255,255), 'lm')
    if met:
        t, a, z, p = met
        d.line([p[0]-45, p[1]-45, p[0]+45, p[1]+45], fill=(63,185,80,255), width=9)
        d.line([p[0]-45, p[1]+45, p[0]+45, p[1]-45], fill=(63,185,80,255), width=9)
        text((p[0]-60, p[1]-40), f'meets the trees {t:%H:%M} · {a:.1f}° up', f_m, (120,230,140,255), 'rb')
    text((40, h-150), 'orange: modelled sun track    red: modelled bare-earth skyline    green: where the track meets the photographed trees',
         f_s, (255,255,255,235))
    text((40, h-80), f'Oldbury Court · photo {t0:%H:%M:%S} BST · camera aimed {cam.yaw/D2R%360:.1f}°, tilted up {cam.pitch/D2R:.1f}°',
         f_s, (255,255,255,235))

    os.makedirs(OUT, exist_ok=True)
    im.resize((w//2, h//2), Image.LANCZOS).save(os.path.join(OUT, outname + '.jpg'), quality=88)

    print(f'\n{outname}')
    if check: print(f'  vs reference trees: d_az {check[1]:+.2f}  d_alt {check[2]:+.2f}  residual {check[0]:.2f}')
    print(f'  sun pixel ({sx:.0f},{sy:.0f})  model alt {alt0:.2f} az {az0:.2f}  camera yaw {cam.yaw/D2R%360:.1f} pitch {cam.pitch/D2R:.1f}')
    if met: print(f'  sun centre meets trees at {met[0]:%H:%M:%S}  alt {met[1]:.2f}  az {met[2]:.1f}')
    for z in range(int(left)+2, int(right)-1, 3):
        p = cam.project(2, z)
        if p and 0 <= p[0] < w and not np.isnan(trees[int(p[0])]):
            ta, _ = cam.unproject(p[0], trees[int(p[0])])
            print(f'    bearing {z:3d}: tree line {ta:5.1f}°   model terrain {hor_at(z) if hor_at(z) is not None else float("nan"):.2f}°')

if __name__ == '__main__':
    shots = {name: prepare(fname, roll) for fname, name, roll, moved in SHOTS}
    for fname, name, roll, moved in SHOTS:
        run(name, shots[name], None if name == REF else align(shots[name]['prof'], shots[REF]['prof']), moved)
