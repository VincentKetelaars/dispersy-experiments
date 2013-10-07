# swift=tribler/Tribler/SwiftEngine/swift
swift=libswift/swift

swift/run_live/source-file.sh ${swift} &
sleep 1
swift/run_live/client.sh ${swift} &
sleep 1
swift/run_live/player.sh  &

sleep 15
pkill swift