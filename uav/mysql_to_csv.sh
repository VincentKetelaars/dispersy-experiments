#!/bin/bash

database=$1
file=$2
table=$3
col=$4

mysql $database -e "SET @file = '${file}', @table = '${table}', @col = '${col}'; SOURCE to_file.sql;"
# mysql your_database --password=foo < my_requests.sql | sed 's/\t/,/g' > out.csv