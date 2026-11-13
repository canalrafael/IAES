#!/bin/sh
SERVER_IP="${1:-192.168.2.1}"

cd /root/ans
echo "[VM2] Starting ANS Client -> Server: $SERVER_IP:5005"

if [ -x /root/ipc_signal ]; then
    /root/ipc_signal write 16 1
fi

python3 client_camera_main.py --ip_address "$SERVER_IP" --dnn_model vgg --video_path models/Golden_Retriever_Hund_Dog.jpg --no_display

if [ -x /root/ipc_signal ]; then
    /root/ipc_signal write 16 0
fi

