import math
from datetime import datetime, timedelta, timezone

LAT, LON = 51.4881038, -2.5302209   # Oldbury Court Estate

def jd(dt):
    dt = dt.astimezone(timezone.utc)
    y, m = dt.year, dt.month
    d = dt.day + (dt.hour + dt.minute/60 + dt.second/3600)/24
    if m <= 2: y -= 1; m += 12
    A = y//100; B = 2 - A + A//4
    return math.floor(365.25*(y+4716)) + math.floor(30.6001*(m+1)) + d + B - 1524.5

def sun_altaz(dt, lat=LAT, lon=LON):
    """NOAA solar position algorithm. Returns (apparent_altitude_deg, azimuth_deg)."""
    JD = jd(dt); T = (JD - 2451545.0)/36525.0
    L0 = (280.46646 + T*(36000.76983 + T*0.0003032)) % 360
    M  = 357.52911 + T*(35999.05029 - 0.0001537*T)
    e  = 0.016708634 - T*(0.000042037 + 0.0000001267*T)
    Mr = math.radians(M)
    C  = (math.sin(Mr)*(1.914602 - T*(0.004817 + 0.000014*T))
          + math.sin(2*Mr)*(0.019993 - 0.000101*T) + math.sin(3*Mr)*0.000289)
    true_long = L0 + C
    omega = 125.04 - 1934.136*T
    app_long = true_long - 0.00569 - 0.00478*math.sin(math.radians(omega))
    eps0 = 23 + (26 + ((21.448 - T*(46.815 + T*(0.00059 - T*0.001813))))/60)/60
    eps = eps0 + 0.00256*math.cos(math.radians(omega))
    epsr, all_ = math.radians(eps), math.radians(app_long)
    dec = math.degrees(math.asin(math.sin(epsr)*math.sin(all_)))
    ra  = math.degrees(math.atan2(math.cos(epsr)*math.sin(all_), math.cos(all_))) % 360
    # equation of time
    y = math.tan(epsr/2)**2
    L0r = math.radians(L0)
    Eot = 4*math.degrees(y*math.sin(2*L0r) - 2*e*math.sin(Mr) + 4*e*y*math.sin(Mr)*math.cos(2*L0r)
                         - 0.5*y*y*math.sin(4*L0r) - 1.25*e*e*math.sin(2*Mr))
    u = dt.astimezone(timezone.utc)
    mins = u.hour*60 + u.minute + u.second/60
    tst = (mins + Eot + 4*lon) % 1440
    ha = tst/4 - 180
    if ha < -180: ha += 360
    har, latr, decr = math.radians(ha), math.radians(lat), math.radians(dec)
    cz = math.sin(latr)*math.sin(decr) + math.cos(latr)*math.cos(decr)*math.cos(har)
    cz = max(-1, min(1, cz)); zen = math.degrees(math.acos(cz))
    alt_true = 90 - zen
    # refraction (NOAA)
    if alt_true > 85: rf = 0
    elif alt_true > 5:
        t_ = math.tan(math.radians(alt_true))
        rf = 58.1/t_ - 0.07/t_**3 + 0.000086/t_**5
    elif alt_true > -0.575:
        a = alt_true
        rf = 1735 + a*(-518.2 + a*(103.4 + a*(-12.79 + a*0.711)))
    else:
        rf = -20.772/math.tan(math.radians(alt_true))
    alt = alt_true + rf/3600
    az_den = math.cos(latr)*math.sin(math.radians(zen))
    if abs(az_den) < 1e-12: az = 180.0
    else:
        ca = (math.sin(latr)*math.cos(math.radians(zen)) - math.sin(decr))/az_den
        ca = max(-1, min(1, ca)); az = math.degrees(math.acos(ca))
        az = (180 + az) % 360 if ha > 0 else (180 - az) % 360
    return alt, az, alt_true

BST = timezone(timedelta(hours=1))
if __name__ == "__main__":
    print(f"{'BST':>8} {'az':>7} {'alt(app)':>9} {'alt(true)':>10}")
    for label, t in [("C1 18:17:06", datetime(2026,8,12,18,17,6,tzinfo=BST)),
                     ("MAX 19:13:45", datetime(2026,8,12,19,13,45,tzinfo=BST)),
                     ("C4 20:07:18", datetime(2026,8,12,20,7,18,tzinfo=BST))]:
        alt, az, at = sun_altaz(t)
        print(f"{label:>13} {az:7.2f} {alt:9.2f} {at:10.2f}")
    print()
    t = datetime(2026,8,12,18,0,0,tzinfo=BST)
    while t <= datetime(2026,8,12,20,50,0,tzinfo=BST):
        alt, az, at = sun_altaz(t)
        print(f"{t:%H:%M} az={az:6.2f} alt={alt:6.2f}")
        t += timedelta(minutes=10)
