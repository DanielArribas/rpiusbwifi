sudo apt update && sudo apt upgrade -y

sudo apt update
sudo apt install git -y
git clone https://github.com/mrfenyx/RPi-Zero-W-WiFi-USB.git
cd RPi-Zero-W-WiFi-USB
sudo chmod +x install.sh
sudo ./install.sh
