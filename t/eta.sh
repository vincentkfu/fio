#!/bin/bash

./fio --name=test --ioengine=null --filesize=1T --time_based --runtime=5 --bandwidth-log
ls -l --full-time agg*
echo "=== ETA should have apeared ==="
read -p "Press enter to continue"

./fio --name=test --ioengine=null --filesize=1T --time_based --runtime=5 --bandwidth-log --eta=never
ls -l --full-time agg*
echo "=== No ETA should have apeared ==="
read -p "Press enter to continue"

./fio --name=test --ioengine=null --filesize=1T --time_based --runtime=5 --bandwidth-log > /dev/null
ls -l --full-time agg*
echo "=== No ETA should have apeared ==="
read -p "Press enter to continue"

./fio --name=test --ioengine=null --filesize=1T --time_based --runtime=5 --bandwidth-log --output-format=terse
ls -l --full-time agg*
echo "=== No ETA should have apeared ==="
read -p "Press enter to continue"

./fio --name=test --ioengine=null --filesize=1T --time_based --runtime=5 --bandwidth-log --output-format=json
ls -l --full-time agg*
echo "=== No ETA should have apeared ==="
read -p "Press enter to continue"
