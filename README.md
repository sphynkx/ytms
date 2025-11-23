[ytms](https://github.com/sphynkx/ytms) is supplemental service for [yurtube app](https://github.com/sphynkx/yurtube). It generates thumbnail preview sprites for uploading videos.

## Install and configure.
Install ffmpeg:
```bash
dnf install ffmpeg
```
Download service from repository and install:
```bash
cd /opt
git clone https://github.com/sphynkx/ytms
cd ytms
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r install/requirements.txt
deactivate
mkdir -p /var/log/uvicorn
cp install/ytms.service /etc/systemd/system/ytms.service
sudo systemctl daemon-reload
sudo systemctl enable --now ytms.service
sudo systemctl status ytms.service
journalctl -u ytms.service -f
```
By default service works with port 8089. you may redefine it by editing `run.sh`. Make sure that current IP and port is in accordance with options in yurtube app configuration.

Check service:
```bash
curl http://localhost:8089/healthz
```
