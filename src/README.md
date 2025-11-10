# RoCam Source Code

The folders and files for this project are as follows:

...
# How to RUN:
cd src\backend && python server.py
cd src\react-app && npm start



# Dev logs
## 10/17/2025
The final ui has 5 major sections: 
Top navigation/status bar (brand, tabs, area/weather/mission/clock).

TOP LEFT: Main camera feed

TOP RIGHT: SEETING

BOTTOM Left: attributes (e.g .Speed, height, iso, lens, shutter, flight time)

BOTTOM RIGHT: gimbal/control pad (arm / dearm,left,up,right,down)

## 10/18/2025
poc only have following features:
TOP LEFT: Main camera feed (nothing else)
BOTTOM RIGHT: gimbal/control pad (arm / dearm,left,up,right,down)
TOP RIGHT: (blank)
BOTTOM Left:(blank)

# 
CODE structure
src\react-app\src\layouts\TwoByTwoGrid.js
src\react-app\src\components\GimbalPad.js
src\react-app\src\components\GimbalStatus.js
src\react-app\src\components\VideoPane.js

src\react-app\src\layouts\TwoByTwoGrid.js
src\react-app\src\lib\gimbalClient.js

src\react-app\src\styles\layout.css
src\react-app\src\styles\theme.css

src\react-app\src\App.js