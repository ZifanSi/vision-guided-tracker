#!/usr/bin/env sh

# Navigate to the same directory as this script
cd "$(dirname "$0")"

sudo nvpmodel -m 2
sudo jetson_clocks
sudo modprobe nvidia-drm modeset=1
sudo chmod 777 /dev/ttyTHS1
sudo setcap 'cap_net_bind_service,cap_sys_nice=+eip' /usr/bin/python3.10

flask run --host=0.0.0.0 -p 80