import os, glob, random, cv2, numpy as np

DATA_ROOT = r".\src\cv\data\Rocket_Tracking.v1i.yolov12"   # has train/, valid/, test/
OUT_ROOT  = r".\src\cv\data\Rocket_Tracking.v1i.yolov12_turns"
ANGLE_RANGE = (-180, 180)
TARGET_W, TARGET_H = 1080, 720

def load_yolo(p):
    if not os.path.exists(p): return []
    rows=[]
    with open(p,"r") as f:
        for ln in f:
            a=ln.strip().split()
            if len(a)==5: rows.append([int(a[0])]+list(map(float,a[1:])))
    return rows

def save_yolo(p, labels):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p,"w") as f:
        for c,cx,cy,w,h in labels:
            f.write(f"{c} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")

def yolo_to_xyxy(lbl,W,H):
    c,cx,cy,w,h = lbl
    x1=(cx-w/2)*W; y1=(cy-h/2)*H
    x2=(cx+w/2)*W; y2=(cy+h/2)*H
    return [c,x1,y1,x2,y2]

def xyxy_to_yolo(c,x1,y1,x2,y2,W,H):
    x1=max(0,x1); y1=max(0,y1); x2=min(W,x2); y2=min(H,y2)
    w=x2-x1; h=y2-y1
    if w<=1 or h<=1: return None
    cx=(x1+x2)/2; cy=(y1+y2)/2
    return [c,cx/W,cy/H,w/W,h/H]

def rotate_bbox_xyxy(x1,y1,x2,y2,M):
    pts=np.array([[x1,y1],[x2,y1],[x2,y2],[x1,y2]],dtype=np.float32)
    pts=np.hstack([pts,np.ones((4,1),dtype=np.float32)])
    rp=(M@pts.T).T
    return rp[:,0].min(),rp[:,1].min(),rp[:,0].max(),rp[:,1].max()

def random_rotate(img, labels_xyxy, angle_range):
    H,W=img.shape[:2]
    angle=random.uniform(*angle_range)
    center=(W/2,H/2)
    M=cv2.getRotationMatrix2D(center,angle,1.0)
    cos, sin = abs(M[0,0]), abs(M[0,1])
    newW=int(W*cos+H*sin); newH=int(H*cos+W*sin)
    M[0,2]+= (newW/2)-center[0]
    M[1,2]+= (newH/2)-center[1]
    rot=cv2.warpAffine(img,M,(newW,newH),flags=cv2.INTER_LINEAR,borderValue=(114,114,114))
    out=[]
    for c,x1,y1,x2,y2 in labels_xyxy:
        nx1,ny1,nx2,ny2=rotate_bbox_xyxy(x1,y1,x2,y2,M)
        nx1,ny1=max(0,nx1),max(0,ny1); nx2,ny2=min(newW,nx2),min(newH,ny2)
        if nx2-nx1>1 and ny2-ny1>1: out.append([c,nx1,ny1,nx2,ny2])
    return rot,out

def letterbox_cap(img, labels_xyxy, tw, th):
    h,w=img.shape[:2]
    if w<=tw and h<=th: return img, labels_xyxy
    r=min(tw/w, th/h)
    nw,nh=int(round(w*r)),int(round(h*r))
    resized=cv2.resize(img,(nw,nh),interpolation=cv2.INTER_LINEAR)
    canvas=np.full((th,tw,3),114,dtype=resized.dtype)
    dw,dh=(tw-nw)//2,(th-nh)//2
    canvas[dh:dh+nh, dw:dw+nw]=resized
    out=[]
    for c,x1,y1,x2,y2 in labels_xyxy:
        x1=x1*r+dw; x2=x2*r+dw; y1=y1*r+dh; y2=y2*r+dh
        if x2-x1>1 and y2-y1>1: out.append([c,x1,y1,x2,y2])
    return canvas,out

def process_split(split_name):
    in_img_dir=os.path.join(DATA_ROOT, split_name, "images")
    in_lbl_dir=os.path.join(DATA_ROOT, split_name, "labels")
    out_img_dir=os.path.join(OUT_ROOT, split_name, "images")
    out_lbl_dir=os.path.join(OUT_ROOT, split_name, "labels")
    os.makedirs(out_img_dir, exist_ok=True); os.makedirs(out_lbl_dir, exist_ok=True)

    paths=sorted(glob.glob(os.path.join(in_img_dir,"*.jpg"))+
                 glob.glob(os.path.join(in_img_dir,"*.png"))+
                 glob.glob(os.path.join(in_img_dir,"*.jpeg")))
    print(f"[{split_name}] images found: {len(paths)} in {os.path.abspath(in_img_dir)}")

    for ip in paths:
        name, ext=os.path.splitext(os.path.basename(ip))
        lp=os.path.join(in_lbl_dir, name+".txt")
        img=cv2.imread(ip); 
        if img is None:
            print(f"  skip (cannot read): {ip}")
            continue
        H,W=img.shape[:2]
        yolo=load_yolo(lp)
        labels_xyxy=[yolo_to_xyxy(l,W,H) for l in yolo]

        img_r,labs_r=random_rotate(img, labels_xyxy, ANGLE_RANGE)
        img_f,labs_f=letterbox_cap(img_r, labs_r, TARGET_W, TARGET_H)

        hF,wF=img_f.shape[:2]
        yolo_out=[]
        for c,x1,y1,x2,y2 in labs_f:
            y=xyxy_to_yolo(c,x1,y1,x2,y2,wF,hF)
            if y: yolo_out.append(y)

        out_img=os.path.join(out_img_dir, f"{name}_rot{ext.lower()}")
        out_lbl=os.path.join(out_lbl_dir, f"{name}_rot.txt")
        cv2.imwrite(out_img, img_f)
        save_yolo(out_lbl, yolo_out)

# Try both 'val' and 'valid' depending on dataset
splits=[]
for s in ["train","valid","test"]:
    if os.path.isdir(os.path.join(DATA_ROOT, s)):
        splits.append(s)

print(os.path.isdir(r"C:\Personal-Project\vision-guided-tracker\src\cv\data\Rocket_Tracking.v1i.yolov12"))
if not splits:
    print("No dataset splits found. Check DATA_ROOT:", os.path.abspath(DATA_ROOT))
else:
    print("Processing splits:", splits)
    for s in splits:
        process_split(s)
    print("Done.")
