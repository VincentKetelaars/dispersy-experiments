export PYTHONPATH=${PYTHONPATH}:/home/vincent/git/MyDispersy

for (( PEER=1; PEER< $1 + 1 ; PEER++ )); do
    python src/main.py &
done
wai$0