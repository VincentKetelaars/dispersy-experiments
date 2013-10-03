export PYTHONPATH=${PYTHONPATH}:${PWD}:${PWD}/tribler

python -m src.tests.unit.testsuite &>~/Desktop/logs5

wait