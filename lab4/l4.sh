#!/bin/bash

make clean

make

for tasks in {2..15}
do
    for counts in {1..5}
    do
        mpirun -np "$tasks" ./l4 500 600 100 100 100 400 0.01 res_2.txt
    done
done


make clean
