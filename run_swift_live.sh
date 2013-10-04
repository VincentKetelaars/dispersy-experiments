swift=tribler/Tribler/SwiftEngine/swift
# swift=libswift/swift

swift/run_live/source-file.sh ${swift} &
swift/run_live/client.sh ${swift} &
swift/run_live/player.sh  &

sleep 10
pkill swift