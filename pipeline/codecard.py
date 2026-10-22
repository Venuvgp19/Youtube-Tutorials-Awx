import sys,re
from PIL import Image, ImageDraw, ImageFont
# Usage: python codecard.py <file> <out.png> <breadcrumb a/b/file> [font size]
import os
F=os.path.join(os.path.dirname(os.path.abspath(__file__)),'fonts')+os.sep
src,out,crumb=sys.argv[1],sys.argv[2],sys.argv[3]
FS=int(sys.argv[4]) if len(sys.argv)>4 else 34
mono=ImageFont.truetype(F+'DejaVuSansMono.ttf',FS)
ui=ImageFont.truetype(F+'Inter-SemiBold.otf',30); uib=ImageFont.truetype(F+'Inter-Bold.otf',30)
lines=open(src).read().rstrip('\n').split('\n')
LH=int(FS*1.45); PADX=50; TOP=110
cw=ImageDraw.Draw(Image.new('RGB',(1,1))).textlength('M',font=mono)
W=int(min(1800,max(900,PADX+70+cw*max(len(l) for l in lines)+60)))
H=TOP+LH*len(lines)+50
im=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(im)
d.rounded_rectangle([0,0,W-1,H-1],26,fill=(16,22,32,255),outline=(255,170,40,255),width=4)
d.rounded_rectangle([2,2,W-3,80],24,fill=(26,34,48,255)); d.rectangle([2,50,W-3,80],fill=(26,34,48,255))
for i,c in enumerate([(255,95,86),(255,189,46),(39,201,63)]): d.ellipse([30+i*40,26,56+i*40,52],fill=c)
pre,name=crumb.rsplit('/',1); pre+=' / '
pre=pre.replace('/',' / ').replace('  ',' ')
d.text((170,22),pre,font=ui,fill=(150,160,180)); x=170+d.textlength(pre,font=ui)
d.text((x,22),name,font=uib,fill=(255,255,255))
C_COM=(120,135,160);C_KEY=(88,230,255);C_STR=(255,230,88);C_DASH=(255,170,40)
y=TOP
for n,l in enumerate(lines,1):
    d.text((PADX-10,y),f'{n:>2}',font=mono,fill=(70,80,100)); x=PADX+70
    if l.strip().startswith('#'): d.text((x,y),l,font=mono,fill=C_COM)
    else:
        ind,dash,key,rest=re.match(r'^(\s*)(- )?([\w:.\-]+:)?(.*)$',l).groups()
        x+=d.textlength(ind or '',font=mono)
        for t,c in ((dash,C_DASH),(key,C_KEY),(rest,C_STR)):
            if t: d.text((x,y),t,font=mono,fill=c); x+=d.textlength(t,font=mono)
    y+=LH
im.save(out); print(im.size)
