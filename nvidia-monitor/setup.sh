sudo mkdir /home/ubuntu/nvidia-monitor/
sudo chown ubuntu /home/ubuntu/nvidia-monitor/
sudo mv nvidia-monitor.py /home/ubuntu/nvidia-monitor
sudo mv nvidia-monitor.service /etc/systemd/system/
sudo systemctl enable nvidia-monitor.service
sudo systemctl start nvidia-monitor.service
sudo systemctl status nvidia-monitor.service
