import os
from pathlib import Path
import cv2
import numpy as np
from time import time

IN_DIR  = Path(r"C:\Personal-Project\vision-guided-tracker\src\cv\data\alot_of_things")
OUT_DIR = Path(r"C:\Personal-Project\vision-guided-tracker\src\cv\runs\motion")
STABILIZE = False  # set True for moving camera compensation

def ensure_parent(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)

def stabilize(prev, curr):
    prev_g = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
    curr_g = cv2.cvtColor(curr, cv2.COLOR_BGR2GRAY)
    p0 = cv2.goodFeaturesToTrack(prev_g, 500, 0.01, 8)
    if p0 is None: 
        return curr
    p1, st, _ = cv2.calcOpticalFlowPyrLK(prev_g, curr_g, p0, None)
    if p1 is None or st is None: 
        return curr
    good_prev, good_curr = p0[st==1], p1[st==1]
    if len(good_prev) < 10: 
        return curr
    M, _ = cv2.estimateAffine2D(good_curr, good_prev, method=cv2.RANSAC, ransacReprojThreshold=3)
    return cv2.warpAffine(curr, M, (curr.shape[1], curr.shape[0])) if M is not None else curr

def process_video(src: Path, dst: Path, stabilize_flag: bool = False):
    print(f"[START] {src}")
    cap = cv2.VideoCapture(str(src))
    if not cap.isOpened():
        print(f"[SKIP] Cannot open: {src}")
        return

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    ensure_parent(dst)
    out = cv2.VideoWriter(str(dst), fourcc, fps, (w, h))

    fgbg = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=True)

    prev = None
    n_frames, t0 = 0, time()
    while True:
        ok, frame = cap.read()
        if not ok:
            break

        if stabilize_flag:
            if prev is None:
                prev = frame.copy()
            frame_stab = stabilize(prev, frame)
            prev = frame_stab
            feed = frame_stab
        else:
            feed = frame

        fg = fgbg.apply(feed)                         # moving=255, shadows ~127
        _, fg = cv2.threshold(fg, 200, 255, cv2.THRESH_BINARY)  # remove shadows
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3,3), np.uint8))
        fg = cv2.morphologyEx(fg, cv2.MORPH_DILATE, np.ones((3,3), np.uint8), iterations=1)

        overlay = frame.copy()
        overlay[fg > 0] = (0, 255, 0)                 # highlight moving pixels
        out.write(overlay)

        n_frames += 1
        if n_frames % 300 == 0:
            elapsed = time() - t0
            print(f"  processed {n_frames} frames ({n_frames/elapsed:.1f} FPS)")

    cap.release(); out.release()
    dur = time() - t0
    print(f"[DONE]  {src.name} → {dst} | frames={n_frames}, avgFPS={n_frames/max(dur,1e-6):.1f}")

def main():
    # mirror structure under OUT_DIR
    mp4s = []
    for root, _, files in os.walk(IN_DIR):
        for f in files:
            if f.lower().endswith(".mp4"):
                src = Path(root) / f
                rel = src.relative_to(IN_DIR)
                dst = OUT_DIR / rel.with_suffix(".mp4")
                mp4s.append((src, dst))

    if not mp4s:
        print(f"No .mp4 files found under: {IN_DIR}")
        return

    print(f"Found {len(mp4s)} video(s). Output root: {OUT_DIR}")
    for src, dst in mp4s:
        process_video(src, dst, stabilize_flag=STABILIZE)

if __name__ == "__main__":
    main()
