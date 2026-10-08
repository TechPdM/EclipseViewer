import json, math
from datetime import datetime, timedelta
from sun import sun_altaz, BST

H0 = 51.0 + 1.6
HOR = """248/0.399/13000/155 249.5/0.43/13000/162 251/0.39/13000/153 252.5/0.398/6000/97
254/0.448/2600/73 255.5/0.52/2500/76 257/0.583/2400/77 258.5/0.659/2300/79
260/0.793/2300/85 261.5/0.853/2200/86 263/0.848/2100/84 264.5/0.937/2000/86
266/1.0/2000/88 267.5/0.983/2000/87 269/0.936/1900/84 270.5/0.894/1900/83
272/0.825/1900/80 273.5/0.789/1900/79 275/0.789/1900/79 276.5/0.791/2200/83
278/0.791/2100/82 279.5/0.808/2100/83 281/0.835/2100/84 282.5/0.862/2100/85
284/0.873/2100/85 285.5/0.889/2000/84 287/0.92/2000/85 288.5/0.926/2000/85
290/0.964/1700/81 291.5/1.1/1600/84 293/1.261/1600/88 294.5/1.442/1500/91
296/1.438/1500/90 297.5/1.383/1600/91 299/1.369/1600/91 300.5/1.333/1600/90
302/1.276/1600/88 303.5/1.2/1600/86 305/1.14/1600/85"""
NEAR = """248/-0.36 249.5/-0.26 251/0.01 252.5/0.24 254/0.41 255.5/0.52 257/0.58 258.5/0.66
260/0.79 261.5/0.85 263/0.85 264.5/0.94 266/1.0 267.5/0.98 269/0.94 270.5/0.89
272/0.82 273.5/0.79 275/0.79 276.5/0.79 278/0.79 279.5/0.81 281/0.83 282.5/0.86
284/0.87 285.5/0.89 287/0.92 288.5/0.93 290/0.96 291.5/1.1 293/1.26 294.5/1.44
296/1.44 297.5/1.38 299/1.37 300.5/1.33 302/1.28 303.5/1.2 305/1.14"""

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
    return max(0.0, (RS+RM-(sep_c + f*(sep_m-sep_c)))/(2*RS))

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

# true sunset AND the moment the sun drops behind the terrain skyline
t = datetime(2026,8,12,19,30,tzinfo=BST); ss=None; ridge=None
while t < datetime(2026,8,12,21,10,tzinfo=BST):
    alt, az, _ = sun_altaz(t)
    if ridge is None and alt <= hor_at(az): ridge=(t.strftime('%H:%M'), round(az,1), round(hor_at(az),2))
    if ss is None and alt <= -0.27: ss=(t.strftime('%H:%M'), round(az,1))
    t += timedelta(seconds=30)

print("Oldbury Court — DEM", H0-1.6, "m | eye", round(H0,1), "m")
print("\nEVENT                          time      sun alt   sun az   horizon   clearance")
for e in events:
    print(f"{e['label']:<30} {e['t']}  {e['alt']:7.2f}  {e['az']:7.2f}  {e['hor']:7.2f}   +{e['clear']:.2f} deg")
print("\nSun drops behind the local ridge:", ridge)
print("True (sea-level) sunset:          ", ss)
mn = min(track, key=lambda p: p['alt']-p['hor'] if 1077<=p['min']<=1207 else 99)
print("Tightest clearance during eclipse:", round(mn['alt']-mn['hor'],2), "at", mn['t'])
json.dump({'H0':round(H0,1),'hor':hor,'track':track,'events':events,
           'sunset':ss,'ridgeset':ridge}, open('analysis.json','w'), indent=0)
