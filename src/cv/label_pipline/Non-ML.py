import cv2

# ======= CONFIG =======
SRC      = r"C:\Users\doubi\Downloads\Carleton_Launch_Sport.mp4"   # "0" for webcam or path to video
DST      = r"C:\Personal-Project\vision-guided-tracker\src\cv\runs\detect\test1.mp4"                 # None to skip saving
TRACKER  = "TLD"                    # "KCF" | "TLD" | "MEDIANFLOW"
MULTI    = False                    # True = select multiple ROIs

# Scaling/display config
FIT_DESKTOP = True                  # auto-fit to screen
MAX_W, MAX_H = None, None           # override screen size if not None (e.g., 1920, 1080)
MARGIN = 120                        # safety margin so window chrome/taskbar don’t clip
UPSCALE = False                     # if True, allows enlarging small videos
WINDOW_NAME = "OpenCV Tracking"
# ======================

def create_tracker(name: str):
    name = name.upper()
    L = getattr(cv2, "legacy", None)
    factories = {
        "KCF":        [getattr(cv2, "TrackerKCF_create", None),
                       getattr(L, "TrackerKCF_create", None) if L else None],
        "TLD":        [getattr(cv2, "TrackerTLD_create", None),
                       getattr(L, "TrackerTLD_create", None) if L else None],
        "MEDIANFLOW": [getattr(cv2, "TrackerMedianFlow_create", None),
                       getattr(L, "TrackerMedianFlow_create", None) if L else None],
    }
    for f in factories.get(name, []):
        if callable(f): return f()
    raise SystemExit(f"{name} tracker unavailable. Install/upgrade opencv-contrib-python.")

def create_multitracker():
    return cv2.legacy.MultiTracker_create() if hasattr(cv2, "legacy") else cv2.MultiTracker_create()

def open_capture(src_str):
    src = 0 if src_str == "0" else src_str
    cap = cv2.VideoCapture(src)
    ok, frame = cap.read()
    if not ok: raise SystemExit("Failed to read first frame.")
    return cap, frame

def _get_screen_size():
    # Prefer tkinter for cross-platform; fall back to ctypes on Windows
    if MAX_W and MAX_H:
        return MAX_W, MAX_H
    if not FIT_DESKTOP:
        return None, None
    try:
        import tkinter as tk
        root = tk.Tk(); root.withdraw()
        w, h = root.winfo_screenwidth(), root.winfo_screenheight()
        root.destroy()
        return w, h
    except Exception:
        try:
            import ctypes
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        except Exception:
            return 1920, 1080  # safe default

def _compute_scale(h, w, desk_w, desk_h):
    if desk_w is None or desk_h is None:
        return 1.0
    desk_w -= MARGIN; desk_h -= MARGIN
    if not UPSCALE:
        return min(desk_w / w, desk_h / h, 1.0)
    return min(desk_w / w, desk_h / h)

def _resize_frame(frame, scale):
    if scale == 1.0: return frame
    h, w = frame.shape[:2]
    new_size = (int(w * scale), int(h * scale))
    return cv2.resize(frame, new_size, interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR)

def create_writer(dst_path, frame_like, cap):
    if not dst_path: return None
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    h, w = frame_like.shape[:2]
    return cv2.VideoWriter(dst_path, fourcc, fps, (w, h))

def main():
    cap, frame0_orig = open_capture(SRC)

    # Compute scale to fit desktop for the FIRST frame; reuse it for all frames
    screen_w, screen_h = _get_screen_size()
    fh, fw = frame0_orig.shape[:2]
    scale = _compute_scale(fh, fw, screen_w, screen_h)
    frame0 = _resize_frame(frame0_orig, scale)

    # Writer uses the scaled frame size (what you see is what you save)
    writer = create_writer(DST, frame0, cap)

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
    if FIT_DESKTOP and (screen_w and screen_h):
        cv2.resizeWindow(WINDOW_NAME, frame0.shape[1], frame0.shape[0])

    # ROI selection on the scaled frame
    if MULTI:
        bboxes = cv2.selectROIs("Select targets (Enter to confirm)", frame0, showCrosshair=True)
        cv2.destroyWindow("Select targets")
        if len(bboxes) == 0: return
        multi = create_multitracker()
        for bb in bboxes:
            tr = create_tracker(TRACKER)
            multi.add(tr, frame0, tuple(bb))
    else:
        bbox = cv2.selectROI("Select target", frame0, fromCenter=False, showCrosshair=True)
        cv2.destroyWindow("Select target")
        if bbox == (0,0,0,0): return
        tracker = create_tracker(TRACKER)
        tracker.init(frame0, bbox)

    # Main loop on scaled frames
    while True:
        ok, frame_orig = cap.read()
        if not ok: break
        frame = _resize_frame(frame_orig, scale)

        if MULTI:
            ok, boxes = multi.update(frame)
            if ok:
                for bb in boxes:
                    x,y,w,h = map(int, bb)
                    cv2.rectangle(frame, (x,y), (x+w,y+h), (0,255,0), 2)
            else:
                cv2.putText(frame, "Tracking lost", (20,40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)
        else:
            ok, bbox = tracker.update(frame)
            if ok:
                x,y,w,h = map(int, bbox)
                cv2.rectangle(frame, (x,y), (x+w,y+h), (0,255,0), 2)
            else:
                cv2.putText(frame, "Tracking lost", (20,40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)

        cv2.putText(frame, TRACKER, (10,25), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)
        cv2.imshow(WINDOW_NAME, frame)
        if writer is not None: writer.write(frame)
        if cv2.waitKey(1) & 0xFF == 27: break  # ESC

    if writer is not None: writer.release()
    cap.release(); cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
