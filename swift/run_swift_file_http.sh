# swift=/home/vincent/git/dispersy-experiments/tribler/Tribler/SwiftEngine/swift 
swift=/home/vincent/git/dispersy-experiments/libswift/swift
swift=/home/vincent/git/libswift/swift
# swift=/usr/share/tribler/swift

${swift} -l 127.0.0.1:12346 -f "/home/vincent/Downloads/small.ogv" -B &>~/Desktop/logs4 &
${swift} -t 127.0.0.1:12346 -g 0.0.0.0:8081 -B &>~/Desktop/logs5 &
chromium-browser http://127.0.0.1:8081/dac3956ab62a6f7761fedf033db1a6ac97e0940f
# Hash: dac3956ab62a6f7761fedf033db1a6ac97e0940f
sleep 10
pkill swift

# Don't forget to check if /tmp already has the file.