/*

Name:  Richard Hoehn
Class: CSCI-6630
Lab:   02
Date:  2026-09-21
Desc:  Hotplate Problem using Threads

*/

// ============================================================================
// A.I. Disclaimer:
// Work for this assignment was completed with the aid of
// artificial intelligence tools and comprehensive documentation of the
// names of, input provided to, and output obtained from, these tools is
// included as part of my assignment submission.
//
// DISCLAIMER of AI Use:
// This custom pthread_barrier implementation was generated using
// Gemini AI to resolve the lack of native pthread_barrier support on macOS.
// Verified and integrated by Richard Hoehn on September 21st, 2026.
// ============================================================================

// Setup Includes & Libs
#include "pthread_barrier.h"
#include <math.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/time.h>

// ============================================================================
// Thread Data
// ============================================================================

typedef struct
{
    int threadId;

    int nRows;
    int nCols;

    int numThreads;

    float epsilon;

    float **gridCurr;
    float **gridNext;

    float *threadDiff;

    pthread_barrier_t *barrier;

    float *diff;
    int *itr;
    int *stop;

} ThreadData;

// ============================================================================
// Functions
// ============================================================================
void writeCsv(const char *fileName, int numThreads, double totalTime) {
    FILE *file = fopen(fileName, "r");

    int fileExists = (file != NULL);

    if (file != NULL) {
        fclose(file);
    }

    file = fopen(fileName, "a");

    if (file == NULL) {
        printf("Error opening CSV file: %s\n", fileName);
        return;
    }

    if (!fileExists) {
        fprintf(file, "os,num_threads,time\n");
    }

    #ifdef __APPLE__
        const char *os = "Apple";
    #elif defined(__linux__)
        const char *os = "Linux";
    #else
        const char *os = "Unknown";
    #endif

    fprintf(file, "%s,%d,%.6f\n", os, numThreads, totalTime);
    fclose(file);
}

void printStatus(int iteration, float diff) {
    printf("%7d   %.6f\n", iteration, diff);
}

void copyGrid(float **src, float **dest, int nRows, int nCols) {
    for (int i = 0; i < nRows; i++) {
        for (int j = 0; j < nCols; j++) {
            dest[i][j] = src[i][j];
        }
    }
}

int isPowerOfTwo(int value) {
    if (value < 1) {
        return 0;
    }

    while (value % 2 == 0) {
        value = value / 2;
    }

    return value == 1;
}

// ============================================================================
// Thread Worker
// ============================================================================

void *threadWorker(void *arg) {
    ThreadData *data = (ThreadData *)arg;

    int threadId = data->threadId;

    int interiorRows = data->nRows - 2;

    // ------------------------------------------------------------------------
    // Divide rows between threads
    // ------------------------------------------------------------------------

    int rowsPerThread = interiorRows / data->numThreads;
    int extraRows = interiorRows % data->numThreads;

    int startRow =
        1 +
        (threadId * rowsPerThread) +
        (threadId < extraRows ? threadId : extraRows);

    int rowCount =
        rowsPerThread +
        (threadId < extraRows ? 1 : 0);

    int endRow = startRow + rowCount;

    // ------------------------------------------------------------------------
    // Wait until ALL threads have been created and are ready
    // ------------------------------------------------------------------------

    pthread_barrier_wait(data->barrier);

    // ------------------------------------------------------------------------
    // Iteration Loop
    // ------------------------------------------------------------------------

    while (1) {
        float localDiff = 0.0f;

        for (int i = startRow; i < endRow; i++) {
            for (int j = 1; j < data->nCols - 1; j++) {
                data->gridNext[i][j] =
                    (data->gridCurr[i - 1][j] +
                     data->gridCurr[i + 1][j] +
                     data->gridCurr[i][j - 1] +
                     data->gridCurr[i][j + 1]) /
                    4.0f;

                float delta = fabsf(data->gridNext[i][j] - data->gridCurr[i][j]);

                if (delta > localDiff) {
                    localDiff = delta;
                }
            }
        }

        // Save this thread's maximum difference
        data->threadDiff[threadId] = localDiff;

        // ====================================================================
        // BARRIER #1
        //
        // Nobody continues until EVERY thread has finished calculating
        // ====================================================================

        pthread_barrier_wait(data->barrier);

        // --------------------------------------------------------------------
        // Thread 0 calculates the GLOBAL maximum difference
        // --------------------------------------------------------------------

        if (threadId == 0) {
            *(data->diff) = 0.0f;

            for (int i = 0; i < data->numThreads; i++) {
                if (data->threadDiff[i] > *(data->diff)) {
                    *(data->diff) = data->threadDiff[i];
                }
            }

            // Print powers of 2
            if (isPowerOfTwo(*(data->itr))) {
                printStatus(*(data->itr), *(data->diff));
            }

            // Determine if converged
            if (*(data->diff) < data->epsilon) {
                *(data->stop) = 1;
            }
        }

        // ====================================================================
        // BARRIER #2
        //
        // Make sure thread 0 finishes calculating the global diff and stop
        // condition before anybody moves on.
        // ====================================================================

        pthread_barrier_wait(data->barrier);

        // --------------------------------------------------------------------
        // Copy this thread's rows from gridNext -> gridCurr
        // --------------------------------------------------------------------

        for (int i = startRow; i < endRow; i++) {
            for (int j = 1; j < data->nCols - 1; j++) {
                data->gridCurr[i][j] = data->gridNext[i][j];
            }
        }

        // ====================================================================
        // BARRIER #3
        //
        // This barrier is especially important.
        //
        // Every thread must finish updating gridCurr BEFORE any thread begins
        // calculating the next iteration.
        // ====================================================================

        pthread_barrier_wait(data->barrier);

        // Stop if converged
        if (*(data->stop)) {
            break;
        }

        // Only original thread updates iteration counter
        if (threadId == 0) {
            (*(data->itr))++;
        }

        // ====================================================================
        // BARRIER #4
        //
        // Keeps the iteration counter synchronized before the next iteration.
        // ====================================================================

        pthread_barrier_wait(data->barrier);
    }

    return NULL;
}

// ============================================================================
// Start Program
// ============================================================================

int main(int argc, char *argv[]) {
    // Setup Constants
    const int minArgCount = 8;
    const int maxArgCount = 9;

    // Setup Vars
    int nRows;
    int nCols;

    float initTop;
    float initBottom;
    float initLeft;
    float initRight;
    float epsilon;
    int numThreads;
    char *csvFileName = NULL;

    // Local Vars
    float diff = 0.0f;

    int itr = 0;
    int stop = 0;

    // ------------------------------------------------------------------------
    // Validate arguments
    // ------------------------------------------------------------------------
    if (argc < (minArgCount + 1) || argc > (maxArgCount + 1)) {
        printf("\n");
        printf("*** Incorrect Argument Count! ***\n");
        printf("\n");
        return -1;
    }

    // ------------------------------------------------------------------------
    // Get Args
    // ------------------------------------------------------------------------

    nRows = atoi(argv[1]);
    nCols = atoi(argv[2]);

    initTop = atof(argv[3]);
    initLeft = atof(argv[4]);
    initRight = atof(argv[5]);
    initBottom = atof(argv[6]);

    epsilon = atof(argv[7]);

    numThreads = atoi(argv[8]);

    if (numThreads < 1) {
        printf("*** Number of threads must be at least 1! ***\n");

        return -1;
    }

    if (argc == 10) {
        csvFileName = argv[9];
    }

    // ------------------------------------------------------------------------
    // Setup Grid
    // ------------------------------------------------------------------------

    float **gridNext = (float **)malloc(nRows * sizeof(float *));

    float **gridCurr = (float **)malloc(nRows * sizeof(float *));

    for (int i = 0; i < nRows; i++) {
        gridNext[i] = (float *)malloc(nCols * sizeof(float));
        gridCurr[i] = (float *)malloc(nCols * sizeof(float));
    }

    // ------------------------------------------------------------------------
    // Setup Walls
    // ------------------------------------------------------------------------

    for (int i = 0; i < nCols; i++) {
        gridCurr[0][i] = initTop;
    }
    for (int i = 0; i < nRows; i++) {
        gridCurr[i][0] = initLeft;
    }
    for (int i = 0; i < nRows; i++) {
        gridCurr[i][nCols - 1] = initRight;
    }
    for (int i = 0; i < nCols; i++) {
        gridCurr[nRows - 1][i] = initBottom;
    }

    // ------------------------------------------------------------------------
    // Get Edge Sum
    // ------------------------------------------------------------------------
    float edgeSum = 0.0f;
    float edgeAvg = 0.0f;

    for (int i = 0; i < nCols; i++) {
        edgeSum += gridCurr[0][i];
        edgeSum += gridCurr[nRows - 1][i];
    }

    for (int i = 1; i < nRows - 1; i++) {
        edgeSum += gridCurr[i][0];
        edgeSum += gridCurr[i][nCols - 1];
    }

    edgeAvg = edgeSum / (2 * nRows + 2 * nCols - 4);

    // ------------------------------------------------------------------------
    // Set Interior to Edge Average
    // ------------------------------------------------------------------------

    for (int i = 1; i < nRows - 1; i++) {
        for (int j = 1; j < nCols - 1; j++) {
            gridCurr[i][j] = edgeAvg;
        }
    }

    // Copy current grid into next grid
    copyGrid(gridCurr, gridNext, nRows, nCols);

    // =========================================================================
    // Setup Threading
    // =========================================================================
    pthread_t *threads = malloc((numThreads - 1) * sizeof(pthread_t));

    ThreadData *threadData = malloc(numThreads * sizeof(ThreadData));

    float *threadDiff = calloc(numThreads, sizeof(float));

    pthread_barrier_t barrier;

    pthread_barrier_init(&barrier, NULL, numThreads);

    // ------------------------------------------------------------------------
    // Initialize data for all threads
    // ------------------------------------------------------------------------

    for (int i = 0; i < numThreads; i++) {
        threadData[i].threadId = i;

        threadData[i].nRows = nRows;
        threadData[i].nCols = nCols;

        threadData[i].numThreads = numThreads;

        threadData[i].epsilon = epsilon;

        threadData[i].gridCurr = gridCurr;
        threadData[i].gridNext = gridNext;

        threadData[i].threadDiff = threadDiff;

        threadData[i].barrier = &barrier;

        threadData[i].diff = &diff;
        threadData[i].itr = &itr;
        threadData[i].stop = &stop;
    }

    // ------------------------------------------------------------------------
    // Create numThreads - 1 workers
    //
    // Main/original thread will be thread 0.
    // ------------------------------------------------------------------------

    for (int i = 1; i < numThreads; i++) {
        pthread_create(&threads[i - 1], NULL, threadWorker, &threadData[i]);
    }

    // =========================================================================
    // Start Timing
    //
    // Initialization and thread creation are NOT included.
    // =========================================================================
    struct timeval startTime;
    struct timeval endTime;

    gettimeofday(&startTime, NULL);

    // ------------------------------------------------------------------------
    // Original/Main thread participates in the work
    // ------------------------------------------------------------------------
    threadWorker(&threadData[0]);
    gettimeofday(&endTime, NULL);

    // ------------------------------------------------------------------------
    // Join worker threads
    // ------------------------------------------------------------------------
    for (int i = 1; i < numThreads; i++) {
        pthread_join(threads[i - 1], NULL);
    }

    // =========================================================================
    // Print Final Result
    // =========================================================================
    printStatus(itr, diff);

    double totalTime = (endTime.tv_sec - startTime.tv_sec) + (endTime.tv_usec - startTime.tv_usec) / 1000000.0;

    printf("\nTOTAL TIME %.6f\n\n", totalTime);

    if (csvFileName != NULL) {
        writeCsv(csvFileName, numThreads, totalTime);
    }

    // =========================================================================
    // Cleanup
    // =========================================================================
    pthread_barrier_destroy(&barrier);

    for (int i = 0; i < nRows; i++) {
        free(gridNext[i]);
        free(gridCurr[i]);
    }

    free(gridNext);
    free(gridCurr);

    free(threadDiff);
    free(threadData);
    free(threads);

    // Exit!
    return 0;
}
