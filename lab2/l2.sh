#!/bin/bash

make clean

make

echo ""
./l2 500 600 100 100 100 400 0.01 1 res_01.txt
./l2 500 600 100 100 100 400 0.01 2 res_01.txt
./l2 500 600 100 100 100 400 0.01 4 res_01.txt
./l2 500 600 100 100 100 400 0.01 8 res_01.txt
./l2 500 600 100 100 100 400 0.01 16 res_01.txt
./l2 500 600 100 100 100 400 0.01 32 res_01.txt


for threads in {1..64}
do
    ./l2 500 600 100 100 100 400 0.01 "$threads" res_02.txt
done


make clean
