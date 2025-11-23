[ytms](https://github.com/sphynkx/ytms) is supplemental service for [yurtube app](https://github.com/sphynkx/yurtube). It generates thumbnail preview sprites for uploading videos.

## Install and configure.
Instructions for Fedora..

### ffmpeg
Install ffmpeg:
```bash
sudo dnf install -y ffmpeg
```
If not found, enable RPM Fusion (free + nonfree), then install:
```bash
sudo dnf install -y https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm  -E %fedora).noarch.rpm https://download1.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm
```
Optionaly - swap ffmpeg-free to full ffmpeg if your system has ffmpeg-free preinstalled:
```bash
sudo dnf -y swap ffmpeg-free ffmpeg --allowerasing
```
Install ffmpeg (ffprobe comes with the same package)
```bash
sudo dnf install -y ffmpeg
```
Verify:
```bash
which ffmpeg && ffmpeg -version
which ffprobe && ffprobe -version
```


### app
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
By default service works with port __8089__. you may redefine it by editing `run.sh`. Make sure that current IP and port is in accordance with options in [yurtube app](https://github.com/sphynkx/yurtube) configuration.

Check service:
```bash
curl http://localhost:8089/healthz
```
