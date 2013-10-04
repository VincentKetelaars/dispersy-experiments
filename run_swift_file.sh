# swift=tribler/Tribler/SwiftEngine/swift 
swift=libswift/swift

${swift} -l 0.0.0.0:12345 -f "/home/vincent/Downloads/small.ogv" &>~/Desktop/logs4 &
${swift} -t 127.0.0.1:12345 -g 0.0.0.0:8081 -w &>~/Desktop/logs5 &
firefox http://127.0.0.1:8081/dac3956ab62a6f7761fedf033db1a6ac97e0940f
# Hash: dac3956ab62a6f7761fedf033db1a6ac97e0940f
sleep 30
pkill swift

# Don't forget to check if /tmp already has the file.