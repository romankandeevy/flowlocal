"""Иконка FlowLocal по сетке иконок macOS: тёмный «сквиркл» 824 из 1024 с
зелёным светом изнутри и бликом по кромке; на нём - светящиеся «буквы»,
которые набегают на текстовый курсор: сказанное ложится туда, где курсор.
Дух - Raycast / Linear: тёмная основа, один смелый символ со свечением.

    backend/.venv/bin/python tools/make_icon.py     ->  Resources/AppIcon.icns

Рисуем через поля расстояний (SDF) и размытие для свечения. Нужен только
numpy; PNG пишется вручную, .icns собирают системные sips и iconutil.
"""
import os
import shutil
import struct
import subprocess
import tempfile
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "Resources", "AppIcon.icns")

N=1024
y,x=np.mgrid[0:N,0:N].astype(np.float32)+0.5
C,HALF=N/2,412.0
def H(h): return np.array([(h>>16)&255,(h>>8)&255,h&255],np.float32)/255
def sq(cx,cy,half,n=5.0):
    u=np.abs(x-cx)/half; v=np.abs(y-cy)/half; f=u**n+v**n-1
    return f/np.maximum(np.hypot(n*u**(n-1)/half,n*v**(n-1)/half),1e-6)
def rr(cx,cy,hw,hh,r):
    qx=np.abs(x-cx)-hw+r; qy=np.abs(y-cy)-hh+r
    return np.hypot(np.maximum(qx,0),np.maximum(qy,0))+np.minimum(np.maximum(qx,qy),0)-r
def seg(ax,ay,bx,by,r):
    px,py=x-ax,y-ay; dx,dy=bx-ax,by-ay; L=dx*dx+dy*dy
    h=np.clip((px*dx+py*dy)/max(L,1e-6),0,1)
    return np.hypot(px-dx*h,py-dy*h)-r
def cover(sd,w=1.0): return np.clip(0.5-sd/w,0,1)
def box(a,r):
    r=int(r)
    if r<1: return a
    for ax in (0,1):
        c=np.cumsum(np.pad(a,[(r+1,r) if i==ax else (0,0) for i in range(2)],mode='edge'),axis=ax)
        if ax==0: a=(c[2*r+1:]-c[:-2*r-1])/(2*r+1)
        else: a=(c[:,2*r+1:]-c[:,:-2*r-1])/(2*r+1)
    return a
def blur(a,r):
    for _ in range(3): a=box(a,r/1.7)
    return a
class Img:
    def __init__(s): s.rgb=np.zeros((N,N,3),np.float32); s.a=np.zeros((N,N),np.float32)
    def over(s,col,m):
        col=np.asarray(col,np.float32)
        if col.ndim==1: col=col[None,None,:]
        m=m[...,None]; s.rgb=col*m+s.rgb*(1-m); s.a=m[...,0]+s.a*(1-m[...,0])
    def add(s,col,m,mask):
        col=np.asarray(col,np.float32)
        if col.ndim==1: col=col[None,None,:]
        s.rgb=np.clip(s.rgb+col*(m*mask)[...,None],0,1)
def lin(c1,c2,t): t=np.clip(t,0,1)[...,None]; return H(c1)*(1-t)+H(c2)*t
def body(img,top=0x1C2622,bot=0x0A0C0B):
    sh=sq(C,C+16,HALF)
    img.over((0,0,0),0.45*np.clip(1-sh/40,0,1)**2*(sh>-1))
    b=sq(C,C,HALF); m=cover(b)
    t=(y-(C-HALF))/(2*HALF)
    col=lin(top,bot,t)
    # мягкое пятно света сверху
    r=np.hypot(x-C,(y-(C-260))*1.2)/520
    col=col+H(0x1F3A2E)[None,None,:]*np.clip(1-r,0,1)[...,None]**2*0.9
    img.over(np.clip(col,0,1),m)
    # кромка: светлая сверху, тёмная снизу
    edge=np.clip(1-np.abs(b+2)/2,0,1)
    img.add((1,1,1),edge*np.clip((C-y)/HALF+0.15,0,1)*0.30,m)
    img.add((1,1,1),np.clip(1-np.abs(b+5)/3,0,1)*0.05,m)
    return m
def glow(img,shape,col,radius,strength,mask):
    g=blur(shape,radius); img.add(H(col),g*strength,mask)
MINT,EM,DEEP,HI=0x8EF0C0,0x2FBF86,0x0E6B4A,0xEFFFF7

def caret():
    img=Img(); m=body(img)
    cx=C+170
    # «буквы» набегают на курсор: тусклые слева, яркие у курсора
    for i,(lx,w,h) in enumerate([(C-300,40,40),(C-215,58,72),(C-112,50,96),(C+2,70,120)]):
        k=0.25+0.25*i
        lm=cover(rr(lx,C+ (60-h/2) ,w/2,h/2,18))
        glow(img,lm,EM,40,0.6*k,m); img.over(H(MINT),lm*m*k)
    caretm=np.maximum(cover(rr(cx,C,30,250,30)),0)
    glow(img,caretm,EM,110,1.4,m); glow(img,caretm,MINT,36,0.9,m)
    img.over(lin(HI,MINT,(y-(C-250))/500),caretm*m)
    img.add((1,1,1),cover(rr(cx-10,C-120,8,110,8))*0.35,m)
    return img

art = caret()
img = np.concatenate([art.rgb * art.a[..., None], art.a[..., None]], axis=2)


def write_png(path, rgba):
    """RGBA 8 бит без фильтров: zlib и три чанка, больше PNG не нужно."""
    a = rgba[..., 3:4]
    rgb = np.where(a > 0, rgba[..., :3] / np.maximum(a, 1e-6), 0)
    px = (np.concatenate([rgb, a], axis=2).clip(0, 1) * 255 + 0.5).astype(np.uint8)
    raw = b"".join(b"\x00" + row.tobytes() for row in px)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    h, w = px.shape[:2]
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(raw, 9)))
        f.write(chunk(b"IEND", b""))


tmp = tempfile.mkdtemp()
try:
    master = os.path.join(tmp, "icon_1024.png")
    write_png(master, img)
    iconset = os.path.join(tmp, "AppIcon.iconset")
    os.mkdir(iconset)
    for size in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            px = size * scale
            name = f"icon_{size}x{size}{'@2x' if scale == 2 else ''}.png"
            subprocess.run(["sips", "-z", str(px), str(px), master, "--out", os.path.join(iconset, name)],
                           check=True, capture_output=True)
    subprocess.run(["iconutil", "-c", "icns", iconset, "-o", OUT], check=True)
    shutil.copy(master, os.path.join(HERE, "..", "build", "icon_1024.png")) if os.path.isdir(
        os.path.join(HERE, "..", "build")) else None
    print("готово:", os.path.normpath(OUT))
finally:
    shutil.rmtree(tmp)
