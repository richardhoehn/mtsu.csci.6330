#!/bin/bash

make clean

make

echo ""
./l1 500 500 0 100 100 100 0.1
echo ""

echo ""
./l1 500 600 100 100 100 400 0.01
echo ""

echo ""
./l1 1500 1600 500 100 150 400 0.01
echo ""
