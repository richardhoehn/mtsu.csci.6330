

How to build and run:
```
(base) jovyan@jupyter-rhoehn:~/lab4$ make clean
rm -f l4 *.o

(base) jovyan@jupyter-rhoehn:~/lab4$ make
/usr/bin/mpicc -O2 -Wall -o l4 l4.c -lm

(base) jovyan@jupyter-rhoehn:~/lab4$ make run
mpirun -np 4 ./l4 500 600 100 100 100 400 0.01
      1   27.254105
      2   17.033783
      4   10.220276
      8   5.881989
     16   3.117508
     32   1.602081
     64   0.810730
    128   0.409241
    256   0.205185
    512   0.102875
   1024   0.051498
   2048   0.025787
   4096   0.012924
   5304   0.009995

TOTAL TIME 0.759958

(base) jovyan@jupyter-rhoehn:~/lab4$ 
```
