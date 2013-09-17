export PYTHONPATH=${PYTHONPATH}:${PWD}:${PWD}/tribler

python -m src.tests.unit.testsuite

wait