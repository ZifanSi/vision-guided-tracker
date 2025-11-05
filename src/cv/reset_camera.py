from src.cv.ct import GimbalSerial


gimbal = GimbalSerial(port="/dev/ttyTHS1", baudrate=115200, timeout=0.5)

gimbal.move_deg(0, 0)