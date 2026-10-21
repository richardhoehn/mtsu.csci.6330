
#include <stdio.h>
#include <stdlib.h>
#include <omp.h>

// Provided by evalfunc.o
extern double evalfunc(int nodeid, int *expandid1, int *expandid2);

// Shared counters
int solutions = 0;
long nodes_examined = 0;
int max_solutions;

// Recursive search
void search(int nodeid) {

    // Stop if enough solutions were found
    int found;

    #pragma omp atomic read
    found = solutions;

    if (found >= max_solutions)
        return;

    // Evaluate node
    int child1 = 0;
    int child2 = 0;

    double value = evalfunc(nodeid, &child1, &child2);

    #pragma omp atomic update
    nodes_examined++;

    // Check for solution
    if (value > 1.0) {

        #pragma omp critical
        {
            if (solutions < max_solutions) {
                solutions++;
                printf("Solution: node %d, value %.6f\n",
                       nodeid, value);
            }
        }
    }

    // Check again before expanding
    #pragma omp atomic read
    found = solutions;

    if (found >= max_solutions)
        return;

    // Search children in parallel
    if (child1 > 0) {
        #pragma omp task firstprivate(child1)
        search(child1);
    }

    if (child2 > 0) {
        #pragma omp task firstprivate(child2)
        search(child2);
    }
}

int main(int argc, char *argv[]) {

    if (argc != 3) {
        printf("Usage: %s T N\n", argv[0]);
        return 1;
    }

    int threads = atoi(argv[1]);
    max_solutions = atoi(argv[2]);

    if (threads < 1 || max_solutions < 1) {
        printf("T and N must be positive integers.\n");
        return 1;
    }

    omp_set_dynamic(0);
    omp_set_num_threads(threads);

    // Begin parallel search
    #pragma omp parallel
    {
        #pragma omp single
        {
            #pragma omp taskgroup
            {
                search(0);
            }
        }
    }

    // Printed once by main thread
    printf("\nSearch complete.\n");
    printf("Solutions found: %d\n", solutions);
    printf("Nodes examined: %ld\n", nodes_examined);

    return 0;
}
