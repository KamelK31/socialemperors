"""Builds villages/plan_grec.json: the Greek mythology kingdom plan (3x3 lands, town hall at 52,52)."""
import json, math, os
cfg=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','config','main.json'))); ITEMS={int(i['id']):i for i in cfg['items']}
LO,HI=20,79                      # 3x3 lands: squares 7,8,9,12,13,14,17,18,19
grid={}                          # (x,y) -> index of placement
P=[]                             # placements: dict(id,x,y,w,h,zone)
ROAD=set()
def size(i): d=ITEMS[i]; return int(d['width']),int(d['height'])
def free(x,y,w,h,pad=0):
    for a in range(x-pad,x+w+pad):
        for b in range(y-pad,y+h+pad):
            if (a,b) in grid or (a,b) in ROAD: return False
    return LO<=x and x+w-1<=HI and LO<=y and y+h-1<=HI
def put(i,x,y,zone):
    w,h=size(i); assert free(x,y,w,h), (ITEMS[i]['name'],x,y)
    P.append(dict(id=i,x=x,y=y,w=w,h=h,zone=zone))
    for a in range(x,x+w):
        for b in range(y,y+h): grid[(a,b)]=len(P)-1
def pack(ids,x0,y0,x1,y1,zone,gap=1):
    "rows of buildings inside [x0,x1]x[y0,y1], 1 free tile around each (paths)"
    left=list(ids); y=y0
    while left and y<=y1:
        x=x0; rowh=0; placed_any=False
        for i in list(left):
            w,h=size(i)
            if x+w-1>x1 or y+h-1>y1: continue
            # find a free spot on this row
            while x+w-1<=x1 and not free(x,y,w,h):
                x+=1
            if x+w-1<=x1 and free(x,y,w,h):
                put(i,x,y,zone); left.remove(i); x+=w+gap; rowh=max(rowh,h); placed_any=True
        y+= (rowh+gap) if placed_any else 1
    return left

TH=26
put(TH,52,52,'acropole')                      # already there in the game
# avenues: 2-tile roads from the town hall to the walls, on its axes
for t in range(LO+1,HI):
    for r in (53,54):
        if not (52<=t<=55): ROAD.add((r,t)); ROAD.add((t,r))

# ---- defense: walls on the border, towers on an inner ring, enhancers mid-sides
WALL,TOWER,ENH=1257,1258,1359
for t in range(LO,HI+1):
    for c in ((t,LO),(t,HI),(LO,t),(HI,t)):
        if c not in grid: put(WALL,c[0],c[1],'defense')
ring=[22,31,40,48,59,67,77]
for a in ring:
    for c in ((a,22),(a,77),(22,a),(77,a)):
        if c not in grid and c not in ROAD: put(TOWER,c[0],c[1],'defense')
for (x,y) in ((24,44),(24,60),(74,44),(74,60),(44,24),(60,24),(44,74),(60,74)):
    put(ENH,x,y,'defense')

# ---- acropolis around the town hall
for (x,y) in ((47,47),(58,47),(47,58),(58,58)): put(61,x,y,'acropole')          # 4 Parthenons
for i,(x,y) in zip((1460,1350,1297,1461),((43,43),(64,43),(43,64),(64,64))): put(i,x,y,'acropole')  # chained gods
for (x,y) in ((50,50),(56,50),(50,56),(56,56)): put(197,x,y,'acropole')        # Healing Springs
for (x,y) in ((47,44),(60,44),(47,63),(60,63)): put(1269 if (x+y)%2 else 1270,x,y,'acropole')
# colonnade along the avenues inside the acropolis
for t in list(range(43,52))+list(range(57,66)):
    for c in ((52,t),(55,t),(t,52),(t,55)):
        if free(*c,1,1) and (t%2==1): put(115,c[0],c[1],'acropole')

# ---- quarters (between the tower ring and the acropolis), each filled up
HOUSE=1260; FIELD=1259; MILL=1256
def fill(first, filler, rects, zone, maxn=200):
    left=list(first)+[filler]*maxn
    for r in rects: left=pack(left,*r,zone)
    return [i for i in left if i!=filler]
# top of the screen (small x, small y): houses
left=fill([], HOUSE, [(24,24,52,41),(24,42,41,52)], 'habitations', 70)
# right (big x, small y): army
left2=fill([1279,1286,1280,1267,1266,1277,1265,1301,1292,1273,1278,1291,1517,1519], 1258,
           [(56,24,75,41),(67,42,75,52)], 'armée', 0)
# left (small x, big y): food
left3=fill([MILL]*8, FIELD, [(24,56,41,75),(42,67,52,75)], 'nourriture', 40)
# bottom (big x, big y): workshops and heroes
left4=fill([150,239,486,1284,189]+[205]*4+[204]*4+[203]*4, MILL, [(56,67,75,75),(67,56,75,66)], 'atelier', 10)
print("not placed:", [ITEMS[i]['name'] for i in left+left2+left3+left4])
json.dump(P,open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','villages','plan_grec.json'),'w'))
from collections import Counter
print(Counter((ITEMS[p['id']]['name'],p['zone']) for p in P))
