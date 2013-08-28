export PYTHONPATH=${PYTHONPATH}:/home/vincent/git/dispersy-experiments/

# This first argument determines the number of instances in 
# the main script
if [ $# -ge 1 ]
then n=$1
else n=1
fi
# This second argument determines whether logging will be 
# shown in the output
if [ $# -eq 2 ]
then log=$2
else log=False
fi

python -O -m src.main -n $n -i $log &

wait