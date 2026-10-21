Log into: `https://jupyterhub.cs.mtsu.edu/azuread`

```
(base) jovyan@jupyter-rhoehn:~/mpi-test$ /usr/bin/mpicc -o mpi_hello mpi_hello.c
(base) jovyan@jupyter-rhoehn:~/mpi-test$ mpirun -np 4 ./mpi_hello
Hello from task 2 on jupyter-rhoehn!
Hello from task 3 on jupyter-rhoehn!
Hello from task 0 on jupyter-rhoehn!
MASTER: Number of MPI tasks is: 4
Hello from task 1 on jupyter-rhoehn!
(base) jovyan@jupyter-rhoehn:~/mpi-test$ ./mpi_hello 
Hello from task 0 on jupyter-rhoehn!
MASTER: Number of MPI tasks is: 1
(base) jovyan@jupyter-rhoehn:~/mpi-test$ mpirun -np 16 ./mpi_hello
Hello from task 13 on jupyter-rhoehn!
Hello from task 14 on jupyter-rhoehn!
Hello from task 15 on jupyter-rhoehn!
Hello from task 1 on jupyter-rhoehn!
Hello from task 5 on jupyter-rhoehn!
Hello from task 6 on jupyter-rhoehn!
Hello from task 7 on jupyter-rhoehn!
Hello from task 8 on jupyter-rhoehn!
Hello from task 10 on jupyter-rhoehn!
Hello from task 11 on jupyter-rhoehn!
Hello from task 12 on jupyter-rhoehn!
Hello from task 0 on jupyter-rhoehn!
MASTER: Number of MPI tasks is: 16
Hello from task 2 on jupyter-rhoehn!
Hello from task 3 on jupyter-rhoehn!
Hello from task 4 on jupyter-rhoehn!
Hello from task 9 on jupyter-rhoehn!
(base) jovyan@jupyter-rhoehn:~/mpi-test$ 
```
