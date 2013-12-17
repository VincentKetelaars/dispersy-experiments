#!/bin/sh
# export PYTHONPATH=.
# sudo apt-get install mysql-server mysql-client python-mysqldb 

mysql -u root -p < create_db.sql
python Tools/ConfigTool.py import Config/defaultConfiguration.xml default
