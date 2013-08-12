export PYTHONPATH=${PYTHONPATH}:/home/vincent/git/dispersy-experiments/

if [ $# -ge 1 ]
then n=$1
else n=1
fi
if [ $# -ge 2 ]
then bool=$2
else bool=True
fi
if [ $# -eq 3 ]
then info=$3
else info=False
fi

for (( PEER=1; PEER< $n + 1 ; PEER++ )); do
    python -O -m src.main -s $bool -i $info &
done
wait