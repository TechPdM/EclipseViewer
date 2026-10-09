"""Compare the model's sun position with photos taken on the day.

The key comparison: mark on the modelled sun track the moment each photo was
taken, and see how far that is from the sun in the photo.

The camera's direction is not recorded, so one photo has to act as the anchor:
the 18:40:29 shot is oriented by fitting the model's sun to its glare. The tree
line it records then orients the other photos, so in those the track is placed
without reference to their own sun and the comparison is a real test.
"""
import json, math, os
from datetime import datetime, timedelta
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ExifTags
from sun import sun_altaz, BST

HERE = os.path.dirname(os.path.abspath(__file__))
PHOTOS = os.path.join(HERE, '..', 'photos')
OUT = os.path.join(PHOTOS, 'overlays')
# roll = camera tilt in degrees (clockwise positive), judged from the far edge of the field
# moved = taken from a different spot to the anchor photo, so nearby trees shift sideways
SHOTS = [('PXL_20260812_174004617.jpg', 'oldbury-court-1840a', 0.0, False),
         ('13b15408-4078-4d34-a309-7ae669ac0c85-1_all_39226.jpg', 'oldbury-court-1840b', 0.0, False),
         ('13b15408-4078-4d34-a309-7ae669ac0c85-1_all_39227.jpg', 'oldbury-court-1900', 0.0, True)]
ANCHOR = 'oldbury-court-1840b'

DATA = json.load(open(os.path.join(HERE, 'analysis.json')))
HOR = DATA['hor']
C1 = datetime(2026,8,12,18,17,6,tzinfo=BST)
MX = datetime(2026,8,12,19,13,45,tzinfo=BST)
C4 = datetime(2026,8,12,20,7,18,tzinfo=BST)
END = datetime(2026,8,12,20,45,tzinfo=BST)
D2R = math.pi/180
SUN_DIAM = 0.53                                  # degrees
FONT = '/System/Library/Fonts/Helvetica.ttc'
WHITE, CYAN, ORANGE, GREEN, RED = (255,255,255,255), (80,225,255,255), (255,140,50,255), (63,185,80,255), (248,81,73,255)

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
        return self

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
    cam = Camera(w, h, f35, roll).pin(sx, sy, alt0, az0)
    trees = tree_line(lum)
    pts = sorted((cam.unproject(x, trees[x])[::-1] for x in range(0, w, 4) if not np.isnan(trees[x])))
    prof = (np.array([p[0] for p in pts]), np.array([p[1] for p in pts]))
    return dict(im=im, t0=t0, f35=f35, roll=roll, sun=(sx, sy), alt0=alt0, az0=az0, cam=cam, trees=trees, prof=prof)

def align(prof, ref, lo=280, hi=303):
    """Shift (d_az, d_alt) that best lays this photo's tree line over the anchor's.
    The range stays right of the sun, clear of the flare."""
    g = np.arange(lo, hi, 0.05); r = np.interp(g, *ref); best = None
    for daz in np.arange(-4, 4.01, 0.05):
        c = np.interp(g, prof[0] + daz, prof[1], left=np.nan, right=np.nan); ok = ~np.isnan(c)
        if ok.sum() < len(g)*0.7: continue
        d = r[ok] - c[ok]; dalt = np.median(d); score = np.mean(np.abs(d - dalt))
        if best is None or score < best[0]: best = (score, daz, dalt)
    return best

def meets_trees(cam, trees, t0, w):
    """First time the sun's centre drops to the photographed tree line."""
    t = t0
    while t <= END:
        a, z, _ = sun_altaz(t); p = cam.project(a, z)
        if p and 0 <= p[0] < w and not np.isnan(trees[int(p[0])]) and p[1] >= trees[int(p[0])]:
            return t, a, z, p
        t += timedelta(seconds=15)

def run(outname, shot, check, moved):
    im, t0, (sx, sy), alt0, az0, trees = (shot[k] for k in ('im','t0','sun','alt0','az0','trees'))
    w, h = im.size
    clean = im.copy()
    own = meets_trees(shot['cam'], trees, t0, w)                # crossing with the photo oriented on its own sun
    if check:                                                   # orient by the anchor's trees, not this photo's sun
        _, daz, dalt = check
        cam = Camera(w, h, shot['f35'], shot['roll']).pin(sx, sy, alt0 + dalt, az0 + daz)
    else:
        daz = dalt = 0.0; cam = shot['cam']
    mx, my = cam.project(alt0, az0)                             # model sun at the moment of the photo
    side = daz*math.cos(alt0*D2R); gap = math.hypot(side, dalt)
    met = meets_trees(cam, trees, t0, w)

    d = ImageDraw.Draw(im, 'RGBA')
    f_s, f_m, f_l, f_xl = (ImageFont.truetype(FONT, s) for s in (44, 54, 64, 84))
    def text(dr, xy, s, font, fill, anchor='la'):
        dr.text(xy, s, font=font, fill=fill, anchor=anchor, stroke_width=5, stroke_fill=(0,0,0,220))
    def polyline(dr, pts, fill, width, dash=None):
        seg = [p for p in pts if p]
        for i in range(len(seg)-1):
            if dash and (i // dash) % 2: continue
            dr.line([seg[i], seg[i+1]], fill=fill, width=width)
    def ring(dr, x, y, r, fill, width):
        dr.ellipse([x-r-3, y-r-3, x+r+3, y+r+3], outline=(0,0,0,255), width=width+6)
        dr.ellipse([x-r, y-r, x+r, y+r], outline=fill, width=width)
    def cross(dr, x, y, r, fill, width):
        for dx, dy in ((1,0),(0,1)):
            dr.line([x-dx*r, y-dy*r, x+dx*r, y+dy*r], fill=(0,0,0,255), width=width+6)
            dr.line([x-dx*r, y-dy*r, x+dx*r, y+dy*r], fill=fill, width=width)

    # --- main picture: altitude lines, modelled terrain, sun track ---
    left, right = cam.unproject(0, h*0.45)[1], cam.unproject(w, h*0.45)[1]
    azs = np.arange(left-3, right+3, 0.25)
    for alt in (0, 5, 10, 15, 20):
        polyline(d, [cam.project(alt, z) for z in azs], (255,255,255,150 if alt == 0 else 80), 5 if alt == 0 else 3,
                 dash=None if alt == 0 else 3)
        p = cam.project(alt, cam.unproject(30, h*0.45)[1])
        if p: text(d, (30, p[1]-8), f'{alt}°' + (' eye level' if alt == 0 else ''), f_s, (255,255,255,230), 'ls')
    polyline(d, [cam.project(hor_at(z), z) for z in azs if hor_at(z) is not None], RED, 6)

    track, t = [], datetime(2026,8,12,18,0,tzinfo=BST)
    while t <= END:
        a, z, _ = sun_altaz(t); track.append((t, cam.project(a, z))); t += timedelta(minutes=1)
    polyline(d, [p for t, p in track if not C1 <= t <= C4], (255,184,77,170), 5)
    polyline(d, [p for t, p in track if C1 <= t <= C4], ORANGE, 9)
    for t, p in track:
        near = min(abs((t-e).total_seconds()) for e in [t0, MX, C4] + ([met[0]] if met else []))
        if p and t.minute % 10 == 0 and 0 < p[0] < w and 0 < p[1] < h and near > 420:
            d.ellipse([p[0]-11, p[1]-11, p[0]+11, p[1]+11], fill=(255,184,77,255))
            text(d, (p[0]+24, p[1]), t.strftime('%H:%M'), f_s, (255,214,150,255), 'lm')
    for lab, tt in (('max 19:13', MX), ('eclipse ends 20:07', C4)):
        a, z, _ = sun_altaz(tt); p = cam.project(a, z)
        if p and 0 < p[0] < w and 0 < p[1] < h:
            ring(d, p[0], p[1], 26, WHITE, 6)
            text(d, (p[0]-40, p[1]+(30 if tt == C4 else 0)), lab, f_m, WHITE, 'rm')
    if met:
        t, a, z, p = met
        d.line([p[0]-45, p[1]-45, p[0]+45, p[1]+45], fill=GREEN, width=9)
        d.line([p[0]-45, p[1]+45, p[0]+45, p[1]-45], fill=GREEN, width=9)
        text(d, (p[0]-60, p[1]-40), f'meets the trees {t:%H:%M} · {a:.1f}° up', f_m, (120,230,140,255), 'rb')

    # --- the key comparison, marked on the track and enlarged below ---
    ring(d, mx, my, 34, CYAN, 8)
    text(d, (mx+60, my-10), f'{t0:%H:%M:%S}  photo taken', f_l, CYAN, 'lm')
    M, crop, side_px = 3, 440, 1320                             # 3x enlargement, about 9° across
    cx0, cy0 = (mx+sx)/2 - crop/2, (my+sy)/2 - crop/2
    px0, py0 = 80, int(h*0.585)
    d.rectangle([40, py0-150, w-40, py0+side_px+50], fill=(0,0,0,175))
    d.rectangle([cx0, cy0, cx0+crop, cy0+crop], outline=WHITE, width=5)
    d.line([cx0, cy0+crop, px0, py0], fill=(255,255,255,170), width=4)
    d.line([cx0+crop, cy0+crop, px0+side_px, py0], fill=(255,255,255,170), width=4)
    text(d, (px0, py0-125), 'KEY COMPARISON', f_xl, WHITE)
    text(d, (px0+830, py0-112), f'where the model puts the sun at {t0:%H:%M:%S}, against the sun in the photo', f_s, WHITE)

    inset = clean.crop((int(cx0), int(cy0), int(cx0)+crop, int(cy0)+crop)).resize((side_px, side_px), Image.LANCZOS)
    di = ImageDraw.Draw(inset, 'RGBA')
    Z = lambda p: ((p[0]-int(cx0))*M, (p[1]-int(cy0))*M) if p else None
    polyline(di, [Z(p) for t, p in track], ORANGE, 8)
    for t, p in track:
        if p and t.minute % 5 == 0 and abs((t-t0).total_seconds()) > 330:
            q = Z(p)
            if 40 < q[0] < side_px-200 and 40 < q[1] < side_px-40:
                di.ellipse([q[0]-12, q[1]-12, q[0]+12, q[1]+12], fill=(255,184,77,255))
                text(di, (q[0]+26, q[1]), t.strftime('%H:%M'), f_s, (255,214,150,255), 'lm')
    qm, qs = Z((mx, my)), Z((sx, sy))
    if gap > 0.15:
        di.line([qm, qs], fill=(0,0,0,255), width=10); di.line([qm, qs], fill=WHITE, width=4)
    ring(di, qm[0], qm[1], SUN_DIAM/2*D2R*cam.F*M, CYAN, 8)     # the sun's disc at true size
    cross(di, qs[0], qs[1], 70, WHITE, 6)
    # labels go on the side away from the other marker
    up = qm[1] <= qs[1]
    model_lab, photo_lab = f'MODEL: the sun at {t0:%H:%M:%S}\n(circle is the sun\'s true size)', 'PHOTO: centre of\nthe sun\'s glare'
    def boxed(xy, s, fill, anchor):                             # label on a dark plate, kept inside the inset
        x0, y0, x1, y1 = di.multiline_textbbox(xy, s, font=f_m, anchor=anchor)
        dx = max(0, 30 - x0) - max(0, x1 - (side_px - 30))
        di.rectangle([x0+dx-16, y0-14, x1+dx+16, y1+14], fill=(0,0,0,200))
        di.multiline_text((xy[0]+dx, xy[1]), s, font=f_m, fill=fill, anchor=anchor)
    if up:
        boxed((qm[0]-40, qm[1]-80), model_lab, CYAN, 'ld')
        boxed((qs[0]+40, qs[1]+100), photo_lab, WHITE, 'ra')
    else:
        boxed((qm[0]+40, qm[1]+70), model_lab, CYAN, 'ra')
        boxed((qs[0]-40, qs[1]-100), photo_lab, WHITE, 'ld')
    im.paste(inset, (px0, py0)); d.rectangle([px0, py0, px0+side_px, py0+side_px], outline=WHITE, width=5)

    tx, ty = px0 + side_px + 70, py0 + 10
    def para(s, font, fill, gap_after=40):
        nonlocal ty
        line = ''
        for word in s.split():
            if d.textlength(line + ' ' + word, font=font) > w - 90 - tx and line:
                text(d, (tx, ty), line, font, fill); ty += font.size*1.25; line = word
            else: line = (line + ' ' + word).strip()
        text(d, (tx, ty), line, font, fill); ty += font.size*1.25 + gap_after
    if check:
        para(f'{gap:.1f}° apart', ImageFont.truetype(FONT, 150), CYAN if gap < SUN_DIAM else (255,200,90,255), 10)
        para(f'{abs(dalt):.1f}° in height, {abs(side):.1f}° sideways. The sun\'s disc is {SUN_DIAM}° wide.', f_m, WHITE)
        para('The track is placed using the trees from the 18:40:29 photo, not this photo\'s own sun, so this is a real test of the model.', f_m, WHITE)
        if moved:
            para('The camera had moved a few metres since 18:40. That shifts the nearby trees sideways and explains the sideways gap; '
                 'height is the fair test here.', f_m, (255,214,150,255))
    else:
        para('Anchor photo', ImageFont.truetype(FONT, 150), WHITE, 10)
        para('The camera\'s direction is not recorded, so the track is fitted to the sun in this photo. The match here is by construction.', f_m, WHITE)
        para('The trees in this photo then place the track in the other two photos, where the comparison is a real test.', f_m, WHITE)

    text(d, (40, h-150), 'orange: modelled sun track    red: modelled bare-earth skyline    green: where the track meets the photographed trees',
         f_s, (255,255,255,235))
    text(d, (40, h-80), f'Oldbury Court · photo {t0:%H:%M:%S} BST · camera aimed {cam.yaw/D2R%360:.1f}°, tilted up {cam.pitch/D2R:.1f}°',
         f_s, (255,255,255,235))

    os.makedirs(OUT, exist_ok=True)
    im.resize((w//2, h//2), Image.LANCZOS).save(os.path.join(OUT, outname + '.jpg'), quality=88)

    print(f'\n{outname}  photo {t0:%H:%M:%S}  model alt {alt0:.2f} az {az0:.2f}')
    if check: print(f'  model vs photo sun: {gap:.2f}° apart  (height {dalt:+.2f}°, sideways {side:+.2f}°)  tree-fit residual {check[0]:.2f}°')
    else: print('  anchor: track fitted to this photo\'s sun')
    if met: print(f'  sun centre meets trees at {met[0]:%H:%M:%S}  alt {met[1]:.2f}  az {met[2]:.1f}')
    if check and own: print(f'  (oriented on its own sun instead: {own[0]:%H:%M:%S})')

if __name__ == '__main__':
    shots = {name: prepare(fname, roll) for fname, name, roll, moved in SHOTS}
    for fname, name, roll, moved in SHOTS:
        run(name, shots[name], None if name == ANCHOR else align(shots[name]['prof'], shots[ANCHOR]['prof']), moved)
