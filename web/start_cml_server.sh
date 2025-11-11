#!/bin/bash
cd /home/robot/programs/common-mechanics-lab/web || exit
source venv/bin/activate

# Alte Logs auf 500 Zeilen begrenzen
if [ -f /home/robot/cml.log ]; then
    tail -n 500 /home/robot/cml.log > /home/robot/cml.tmp
    mv /home/robot/cml.tmp /home/robot/cml.log
fi

echo "--- Start: $(date) ---" >> /home/robot/cml.log
python3 flask-server.py >> /home/robot/cml.log 2>&1
