import json, math
from datetime import datetime, timedelta
from sun import sun_altaz, BST

H0 = 71.1 + 1.6
HOR = """248/0.248/14000/147 249.5/0.12/14000/116 251/-0.034/13500/77 252.5/0.01/10500/82
254/0.221/9000/113 255.5/0.419/10500/157 257/0.385/10000/147 258.5/0.404/10500/154
260/0.4/10000/149 261.5/0.467/9000/152 263/0.45/9000/149 264.5/0.386/12000/163
266/0.354/12000/157 267.5/0.345/12000/155 269/0.292/8000/118 270.5/0.3/8000/119
272/0.249/7500/109 273.5/0.237/7500/108 275/0.232/7000/104 276.5/0.179/7000/98
278/0.107/7500/91 279.5/0.098/6500/87 281/0.112/6500/88 282.5/0.125/6000/88
284/0.194/6000/96 285.5/0.189/6000/95 287/0.198/6000/96 288.5/0.181/6000/94
290/0.207/6000/97 291.5/0.2/6000/96 293/0.163/6000/92 294.5/0.181/46000/363
296/0.234/44000/384 297.5/0.084/44000/269 299/0.249/44000/396 300.5/0.287/44000/425
302/0.32/44000/450 303.5/0.331/44000/459 305/0.198/48000/396"""
NEAR = """248/-1.47 249.5/-1.46 251/-1.46 252.5/-1.47 254/-1.48 255.5/-1.47 257/-1.43 258.5/-1.38
260/-1.35 261.5/-1.34 263/-1.31 264.5/-1.3 266/-1.24 267.5/-1.25 269/-1.28 270.5/-1.3
272/-1.26 273.5/-1.2 275/-1.1 276.5/-1.18 278/-1.21 279.5/-1.21 281/-1.19 282.5/-1.16
284/-1.15 285.5/-1.12 287/-1.1 288.5/-1.1 290/-1.11 291.5/-1.12 293/-1.13 294.5/-1.13
296/-1.11 297.5/-1.08 299/-0.94 300.5/-0.83 302/-0.89 303.5/-0.92 305/-0.88"""

hor = [dict(zip(('az','alt','d','h'), (float(a),float(b),float(c),float(dd))))
       for a,b,c,dd in (s.split('/') for s in HOR.split())]
near = {float(a): float(b) for a,b in (s.split('/') for s in NEAR.split())}
for r in hor: r['near'] = near[r['az']]

def hor_at(az):
    if az <= hor[0]['az']: return hor[0]['alt']
    if az >= hor[-1]['az']: return hor[-1]['alt']
    for i in range(len(hor)-1):
        if hor[i]['az'] <= az <= hor[i+1]['az']:
            f = (az-hor[i]['az'])/(hor[i+1]['az']-hor[i]['az'])
            return hor[i]['alt'] + f*(hor[i+1]['alt']-hor[i]['alt'])

C1 = datetime(2026,8,12,18,17,6,tzinfo=BST)
MX = datetime(2026,8,12,19,13,45,tzinfo=BST)
C4 = datetime(2026,8,12,20,7,18,tzinfo=BST)

def mag(t):
    if t <= C1 or t >= C4: return 0.0
    RS, RM, mmax = 1.0, 1.02, 0.937
    sep_c, sep_m = RS+RM, (RS+RM) - 2*mmax*RS
    f = ((t-C1)/(MX-C1)) if t <= MX else ((C4-t)/(C4-MX))
    sep = sep_c + f*(sep_m-sep_c)
    return max(0.0, (RS+RM-sep)/(2*RS))

track = []
t = datetime(2026,8,12,18,0,tzinfo=BST)
while t <= datetime(2026,8,12,20,45,tzinfo=BST):
    alt, az, _ = sun_altaz(t)
    track.append({'t': t.strftime('%H:%M'), 'min': t.hour*60+t.minute,
                  'alt': round(alt,3), 'az': round(az,3),
                  'hor': round(hor_at(az),3), 'mag': round(mag(t),3)})
    t += timedelta(minutes=5)

events = []
for lab, tt in [('Partial eclipse begins (C1)',C1), ('Maximum eclipse (0.937 mag)',MX),
                ('Partial eclipse ends (C4)',C4)]:
    alt, az, _ = sun_altaz(tt)
    events.append({'label':lab,'t':tt.strftime('%H:%M:%S'),'alt':round(alt,2),
                   'az':round(az,2),'hor':round(hor_at(az),2),
                   'clear':round(alt-hor_at(az),2)})

# sunset: apparent alt of centre = -0.27 (upper limb touching, refraction incl.)
t = datetime(2026,8,12,20,20,tzinfo=BST); ss=None
while t < datetime(2026,8,12,21,10,tzinfo=BST):
    alt, az, _ = sun_altaz(t)
    if alt <= -0.27: ss=(t.strftime('%H:%M'), round(az,1)); break
    t += timedelta(seconds=30)

print("SUMMIT (DEM):", H0-1.6, "m  eye:", H0, "m")
print("\nEVENT                          time      sun alt   sun az   horizon   clearance")
for e in events:
    print(f"{e['label']:<30} {e['t']}  {e['alt']:7.2f}  {e['az']:7.2f}  {e['hor']:7.2f}   +{e['clear']:.2f} deg")
print("\nSunset:", ss)
print("\nWorst clearance over eclipse:", min(round(p['alt']-p['hor'],2) for p in track
      if 1077 <= p['min'] <= 1207))
json.dump({'H0':H0,'hor':hor,'track':track,'events':events,'sunset':ss},
          open('analysis.json','w'), indent=0)
