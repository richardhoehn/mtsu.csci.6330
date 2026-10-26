/*
Name:  Richard Hoehn
Class: CSCI-6630
Lab:   04
Date:  2026-10-26
Desc:  Hotplate Problem using MPI shared memory (manager / workers)
*/

// ============================================================================
// A.I. Disclaimer:
//
// I used ChatGPT to help adapt my earlier pthread hotplate program (Lab 2)
// to MPI for this assignment. In particular, I needed help understanding
// MPI shared-memory windows and how separate MPI processes can access the
// same grid when they all run on one computer.
//
// ChatGPT helped explain and develop the shared-memory implementation using
// MPI_Comm_split_type, MPI_Win_allocate_shared, MPI_Win_shared_query, and
// MPI_Win_sync. It also helped with process synchronization (MPI_Barrier),
// collecting the largest temperature change (MPI_Reduce), and sharing the
// stopping decision (MPI_Bcast). I used the explanations to understand the
// differences between pthreads and MPI, and tested the program myself.
//
// This version includes AI-assisted code and comments, which I reviewed
// and modified as part of the assignment.
// ============================================================================

#include <mpi.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

static int isPowerOfTwo(int value)
{
    return value > 0 && (value & (value - 1)) == 0;
}

static void printStatus(int iteration, float diff)
{
    printf("%7d   %.6f\n", iteration, diff);
}

static void writeCsv(const char *fileName, int numRanks, double totalTime)
{
    FILE *file = fopen(fileName, "r");
    int fileExists = (file != NULL);
    if (file)
        fclose(file);

    file = fopen(fileName, "a");
    if (!file)
    {
        printf("Error opening CSV file: %s\n", fileName);
        return;
    }
    if (!fileExists)
        fprintf(file, "os,num_ranks,time\n");
#ifdef __APPLE__
    const char *os = "Apple";
#elif defined(__linux__)
    const char *os = "Linux";
#else
    const char *os = "Unknown";
#endif
    fprintf(file, "%s,%d,%.6f\n", os, numRanks, totalTime);
    fclose(file);
}

static void initializeGrid(float *grid, int nRows, int nCols,
                           float top, float left, float right, float bottom)
{
    for (int j = 0; j < nCols; j++)
        grid[j] = top;
    for (int i = 0; i < nRows; i++)
        grid[(size_t)i * nCols] = left;
    for (int i = 0; i < nRows; i++)
        grid[(size_t)i * nCols + nCols - 1] = right;
    for (int j = 0; j < nCols; j++)
        grid[(size_t)(nRows - 1) * nCols + j] = bottom;

    float edgeSum = 0.0f;
    for (int j = 0; j < nCols; j++)
    {
        edgeSum += grid[j];
        edgeSum += grid[(size_t)(nRows - 1) * nCols + j];
    }
    for (int i = 1; i < nRows - 1; i++)
    {
        edgeSum += grid[(size_t)i * nCols];
        edgeSum += grid[(size_t)i * nCols + nCols - 1];
    }
    float edgeAvg = edgeSum / (2 * nRows + 2 * nCols - 4);
    for (int i = 1; i < nRows - 1; i++)
        for (int j = 1; j < nCols - 1; j++)
            grid[(size_t)i * nCols + j] = edgeAvg;
}

int main(int argc, char *argv[])
{
    // Required for every rank, including the manager.
    alarm(180);
    MPI_Init(&argc, &argv);

    int rank, numRanks;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &numRanks);

    if (numRanks < 2 || argc < 8 || argc > 9)
    {
        if (rank == 0)
        {
            printf("Usage: mpiexec -n R ./l4 rows cols top left right bottom epsilon [csv_file]\n");
            printf("R must be at least 2.\n");
        }
        MPI_Finalize();
        return EXIT_FAILURE;
    }

    int nRows = atoi(argv[1]);
    int nCols = atoi(argv[2]);
    float initTop = (float)atof(argv[3]);
    float initLeft = (float)atof(argv[4]);
    float initRight = (float)atof(argv[5]);
    float initBottom = (float)atof(argv[6]);
    float epsilon = (float)atof(argv[7]);
    const char *csvFileName = (argc == 9) ? argv[8] : NULL;

    if (nRows < 3 || nCols < 3 || !isfinite(epsilon) || epsilon <= 0.0f)
    {
        if (rank == 0)
            printf("Error: rows and cols must be >= 3 and epsilon must be positive.\n");
        MPI_Finalize();
        return EXIT_FAILURE;
    }

    // Each worker computes some interior rows; rank 0 only manages.
    int interiorRows = nRows - 2;
    int activeWorkers = (numRanks - 1 < interiorRows) ? numRanks - 1 : interiorRows;
    int myStart = 1, myRows = 0;
    if (rank >= 1 && rank <= activeWorkers)
    {
        int worker = rank - 1;
        int baseRows = interiorRows / activeWorkers;
        int extraRows = interiorRows % activeWorkers;
        myRows = baseRows + (worker < extraRows ? 1 : 0);
        myStart = 1 + worker * baseRows + (worker < extraRows ? worker : extraRows);
    }

    // ============================================================================
    // MPI Shared Memory
    //
    // Normally, MPI processes have separate memory spaces and must exchange
    // data using MPI_Send and MPI_Recv.
    //
    // Since all ranks in this project run on the same machine, we can use
    // MPI shared memory instead.
    //
    // MPI_Comm_split_type groups ranks that are able to share memory.
    // This lets workers access the same hotplate grid directly.
    // ============================================================================
    MPI_Comm sharedComm;
    MPI_Comm_split_type(MPI_COMM_WORLD, MPI_COMM_TYPE_SHARED, rank,
                        MPI_INFO_NULL, &sharedComm);
    int sharedRanks;
    MPI_Comm_size(sharedComm, &sharedRanks);
    if (sharedRanks != numRanks)
    {
        if (rank == 0)
            printf("Error: all MPI ranks must run on one shared-memory node.\n");
        MPI_Abort(MPI_COMM_WORLD, EXIT_FAILURE);
    }

    // Allocate TWO grids in one MPI shared-memory window.
    // Rank 0 allocates the storage; other ranks query its address.
    size_t cells = (size_t)nRows * (size_t)nCols;
    if (cells > SIZE_MAX / (2 * sizeof(float)) ||
        cells > (size_t)PTRDIFF_MAX / (2 * sizeof(float)))
    {
        if (rank == 0)
            printf("Error: grid dimensions too large.\n");
        MPI_Abort(MPI_COMM_WORLD, EXIT_FAILURE);
    }

    // ============================================================================
    // Allocate Shared Grid
    //
    // MPI_Win_allocate_shared creates memory that can be accessed by
    // multiple MPI processes on the same machine.
    //
    // We allocate enough space for two complete grids:
    //   curr - Current temperature values
    //   next - Updated temperature values
    //
    // Only rank 0 allocates the actual storage. Other ranks request
    // zero bytes because they will access rank 0's shared allocation.
    // ============================================================================
    MPI_Aint bytes = (rank == 0) ? (MPI_Aint)(2 * cells * sizeof(float)) : 0;
    float *localBase = NULL;
    MPI_Win window;
    MPI_Win_allocate_shared(bytes, sizeof(float), MPI_INFO_NULL,
                            sharedComm, &localBase, &window);

    // ============================================================================
    // Access Shared Memory
    //
    // MPI_Win_shared_query obtains a pointer to the memory allocated
    // by rank 0.
    //
    // Each process may have a different pointer address, but they all
    // access the same underlying shared grid.
    //
    // This eliminates the need to send neighboring rows between workers.
    // ============================================================================
    MPI_Aint queriedBytes;
    int displacementUnit;
    float *sharedBase = NULL;
    MPI_Win_shared_query(window, 0, &queriedBytes, &displacementUnit,
                         &sharedBase);
    if (!sharedBase || queriedBytes < (MPI_Aint)(2 * cells * sizeof(float)))
    {
        if (rank == 0)
            printf("Error: could not access shared grid.\n");
        MPI_Abort(MPI_COMM_WORLD, EXIT_FAILURE);
    }

    float *curr = sharedBase;
    float *next = sharedBase + cells;

    if (rank == 0)
    {
        initializeGrid(curr, nRows, nCols, initTop, initLeft, initRight, initBottom);
        for (size_t k = 0; k < cells; k++)
            next[k] = curr[k];
    }

    // ============================================================================
    // Synchronize Shared Memory
    //
    // MPI_Win_sync helps ensure that memory updates are visible through
    // the MPI shared-memory window.
    //
    // MPI_Barrier waits until all ranks have reached the same point.
    //
    // Together, these operations ensure the initialized grid is ready
    // before workers begin calculating temperatures.
    // ============================================================================
    MPI_Win_sync(window);
    MPI_Barrier(sharedComm);
    MPI_Win_sync(window);

    double startTime = MPI_Wtime();
    int itr = 0, stop = 0;
    float diff = 0.0f;

    while (!stop)
    {
        float localDiff = 0.0f;

        // ============================================================================
        // Calculate Hotplate Temperatures
        //
        // Each worker calculates only its assigned interior rows.
        //
        // Because the grid is shared, workers can directly read neighboring
        // cells, even when those cells belong to another worker's rows.
        //
        // The new temperature is the average of the four neighboring cells.
        // localDiff tracks the largest temperature change for this worker.
        //
        // Unlike the original MPI implementation, no halo rows are needed.
        // ============================================================================
        if (rank >= 1 && rank <= activeWorkers)
        {
            for (int i = myStart; i < myStart + myRows; i++)
            {
                for (int j = 1; j < nCols - 1; j++)
                {
                    size_t k = (size_t)i * nCols + j;
                    next[k] = (curr[k - nCols] + curr[k + nCols] +
                               curr[k - 1] + curr[k + 1]) /
                              4.0f;
                    float delta = fabsf(next[k] - curr[k]);
                    if (delta > localDiff)
                        localDiff = delta;
                }
            }
        }

        // Make writes to 'next' visible, and wait for all workers.
        // MPI_Barrier by itself is not a substitute for MPI_Win_sync.
        MPI_Win_sync(window);
        MPI_Barrier(sharedComm);
        MPI_Win_sync(window);

        // ============================================================================
        // Check Convergence
        //
        // Each worker calculates its largest temperature change (localDiff).
        //
        // MPI_Reduce finds the maximum difference across all ranks and
        // sends the result to rank 0.
        //
        // Rank 0 checks whether the maximum difference is less than epsilon.
        //
        // MPI_Bcast shares the stopping decision with every rank.
        // ============================================================================
        MPI_Reduce(&localDiff, &diff, 1, MPI_FLOAT, MPI_MAX, 0, MPI_COMM_WORLD);
        if (rank == 0)
        {
            if (isPowerOfTwo(itr))
                printStatus(itr, diff);
            stop = (diff < epsilon);
        }
        MPI_Bcast(&stop, 1, MPI_INT, 0, MPI_COMM_WORLD);

        // ============================================================================
        // Swap Grids
        //
        // Instead of copying the entire updated grid back to the current
        // grid, we simply swap the two pointers.
        //
        // This is more efficient and allows the next iteration to use
        // the newly calculated temperatures.
        //
        // Every rank must swap its pointers to remain consistent.
        // ============================================================================
        float *temp = curr;
        curr = next;
        next = temp;
        if (!stop)
            itr++;
    }

    double localTime = MPI_Wtime() - startTime;
    double totalTime = 0.0;

    // ============================================================================
    // Measure Execution Time
    //
    // Each rank measures its execution time using MPI_Wtime.
    //
    // MPI_Reduce collects the longest execution time using MPI_MAX.
    // This allows rank 0 to report the time of the slowest process.
    //
    // Only rank 0 prints the results and writes the optional CSV file.
    // ============================================================================
    MPI_Reduce(&localTime, &totalTime, 1, MPI_DOUBLE, MPI_MAX, 0,
               MPI_COMM_WORLD);
    if (rank == 0)
    {
        printStatus(itr, diff);
        printf("\nTOTAL TIME %.6f\n\n", totalTime);
        if (csvFileName)
            writeCsv(csvFileName, numRanks, totalTime);
    }

    // ============================================================================
    // Cleanup
    //
    // MPI_Win_free releases the shared-memory allocation.
    //
    // MPI_Comm_free releases the shared-memory communicator.
    //
    // Unlike malloc(), shared MPI memory should not be released using free().
    //
    // MPI_Finalize shuts down the MPI environment for this process.
    // ============================================================================
    MPI_Win_free(&window);
    MPI_Comm_free(&sharedComm);
    MPI_Finalize();
    return 0;
}
