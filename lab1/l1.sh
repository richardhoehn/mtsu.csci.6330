#!/bin/bash

make clean

make

echo ""
./l1 500 500 0 100 100 100 0.1
echo ""

echo ""
./l1 50 160 111 222 333 444 0.01
echo ""

make clean
