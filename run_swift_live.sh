swift=tribler/Tribler/SwiftEngine/swift # HTTPGW Uses FileTransfer
# swift=libswift/swift # HTTPGW can use LiveTransfer if '@-1' appended. VLC fails though then.

swift/run_live/source-file.sh ${swift} &>~/Desktop/logs4 &
swift/run_live/client.sh ${swift} &>~/Desktop/logs5 &
swift/run_live/player.sh  &

sleep 10
pkill vlc
pkill swift