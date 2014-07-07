swift=/home/vincent/git/libswift/swift  # HTTPGW Uses FileTransfer
# swift=/home/vincent/git/dispersy-experiments/libswift/swift # HTTPGW can use LiveTransfer if '@-1' appended. VLC fails though then.

run_live/source-file.sh ${swift} &>~/Desktop/logs4 &
run_live/client.sh ${swift} &>~/Desktop/logs5 &
run_live/player.sh  &

sleep 10
pkill vlc
pkill swift