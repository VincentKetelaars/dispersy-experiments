export PYTHONPATH=${PYTHONPATH}:/home/vincent/git/dispersy-experiments/

# This first argument determines the number of calls to 
# the main script
if [ $# -ge 1 ]
then n=$1
else n=1
fi
# This second argument determines whether the single
# or multi dispersy instance is called
if [ $# -ge 2 ]
then bool=$2
else bool=True
fi
# This third argument determines whether statistics will be 
# shown in the output
if [ $# -eq 3 ]
then info=$3
else info=False
fi

for (( PEER=1; PEER< $n + 1 ; PEER++ )); do
    python -O -m src.main -s $bool -i $info &
done
wait