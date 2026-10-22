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

Here is another test:
```
(base) jovyan@jupyter-rhoehn:~/mpi-test$ /usr/bin/mpicc -o mpi_helloBsend mpi_helloBsend.c
(base) jovyan@jupyter-rhoehn:~/mpi-test$ ./mpi_helloBsend 
Quitting. Need an even number of tasks: numtasks=1
(base) jovyan@jupyter-rhoehn:~/mpi-test$ ./mpi_helloBsend -numtasks=2
Quitting. Need an even number of tasks: numtasks=1
(base) jovyan@jupyter-rhoehn:~/mpi-test$ ./mpi_helloBsend 4
Quitting. Need an even number of tasks: numtasks=1
(base) jovyan@jupyter-rhoehn:~/mpi-test$ mpirun -np 16 ./mpi_helloBsend
Hello from task 12 on jupyter-rhoehn!
Task 12 is partner with 4
Hello from task 13 on jupyter-rhoehn!
Task 13 is partner with 5
Hello from task 14 on jupyter-rhoehn!
Task 14 is partner with 6
Hello from task 15 on jupyter-rhoehn!
Task 15 is partner with 7
Hello from task 3 on jupyter-rhoehn!
Task 3 is partner with 11
Hello from task 4 on jupyter-rhoehn!
Task 4 is partner with 12
Hello from task 5 on jupyter-rhoehn!
Task 5 is partner with 13
Hello from task 6 on jupyter-rhoehn!
Task 6 is partner with 14
Hello from task 7 on jupyter-rhoehn!
Task 7 is partner with 15
Hello from task 8 on jupyter-rhoehn!
Task 8 is partner with 0
Hello from task 9 on jupyter-rhoehn!
Task 9 is partner with 1
Hello from task 11 on jupyter-rhoehn!
Task 11 is partner with 3
MASTER: Number of MPI tasks is: 16
Hello from task 0 on jupyter-rhoehn!
Task 0 is partner with 8
Hello from task 1 on jupyter-rhoehn!
Task 1 is partner with 9
Hello from task 2 on jupyter-rhoehn!
Task 2 is partner with 10
Hello from task 10 on jupyter-rhoehn!
Task 10 is partner with 2
(base) jovyan@jupyter-rhoehn:~/mpi-test$ 
```
