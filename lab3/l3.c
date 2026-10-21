
/*

Name:  Richard Hoehn
Class: CSCI-6630
Lab:   03
Date:  2026-10-21
Desc:  Parallel Tree Search using OpenMP

*/

// ============================================================================
// A.I. Disclaimer:
//
// This assignment was completed with the assistance of AI tools.
//
// ChatGPT (OpenAI) was used to help understand and document the OpenMP
// implementation, including tasks, atomic operations, and critical sections.
//
// AI assistance was also used to troubleshoot the Makefile so that the
// program could compile and run on macOS with OpenMP support.
//
// Additionally, ChatGPT helped identify Windows-style line endings (CRLF)
// in the T1, T2, and T3 test scripts that caused execution issues on macOS.
//
// The code was reviewed, compiled, and tested by Richard Hoehn.
// ============================================================================

#include <stdio.h>
#include <stdlib.h>
#include <omp.h>

// This function is provided by the assignment.
// It evaluates a node and returns the IDs of its two children.
extern double evalfunc(int nodeid, int *expandid1, int *expandid2);

// These variables are shared by all threads.
// They track the number of solutions, nodes examined, and when to stop.
int solutions = 0;
long nodes_examined = 0;
int max_solutions;


// Search the tree starting at the given node.
void search(int nodeid) {

    // Before doing any work, check if we already found enough solutions.
    // Atomic read ensures we safely read the shared counter.
    int found;

    #pragma omp atomic read
    found = solutions;

    if (found >= max_solutions)
        return;

    // Evaluate the current node and get its two possible children.
    int child1 = 0;
    int child2 = 0;

    double value = evalfunc(nodeid, &child1, &child2);

    // Count this node as examined.
    // Atomic update prevents multiple threads from losing increments.
    #pragma omp atomic update
    nodes_examined++;

    // A value greater than 1.0 means this node is a solution.
    if (value > 1.0) {

        // Only one thread can update the solution count at a time.
        // This also prevents us from reporting more solutions than requested.
        #pragma omp critical
        {
            if (solutions < max_solutions) {
                solutions++;

                printf("Solution: node %d, value %.6f\n",
                       nodeid, value);
            }
        }
    }

    // Check again before searching the children.
    // Another thread may have found enough solutions while we were working.
    #pragma omp atomic read
    found = solutions;

    if (found >= max_solutions)
        return;

    // Create separate OpenMP tasks for each valid child.
    // This allows different threads to explore different parts of the tree.
    // firstprivate gives each task its own copy of the child ID.
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

    // The program needs two arguments:
    // T = number of threads
    // N = maximum number of solutions to find.
    if (argc != 3) {
        printf("Usage: %s T N\n", argv[0]);
        return 1;
    }

    // Read the requested number of threads and solutions.
    int threads = atoi(argv[1]);
    max_solutions = atoi(argv[2]);

    // Both arguments must be positive numbers.
    if (threads < 1 || max_solutions < 1) {
        printf("T and N must be positive integers.\n");
        return 1;
    }

    // Use the exact number of threads requested.
    // Disable OpenMP's automatic adjustment of the thread count.
    omp_set_dynamic(0);
    omp_set_num_threads(threads);

    // Start the parallel search using the requested threads.
    #pragma omp parallel
    {
        // Only one thread starts the search at node 0.
        // Other threads are available to help process tasks.
        #pragma omp single
        {
            // Wait until all search tasks have completed.
            #pragma omp taskgroup
            {
                search(0);
            }
        }
    }

    // Once all threads have finished, print the final results.
    // This section runs only once after the parallel region ends.
    printf("\nSearch complete.\n");
    printf("Solutions found: %d\n", solutions);
    printf("Nodes examined: %ld\n", nodes_examined);

    return 0;
}
