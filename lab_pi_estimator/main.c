
/*

Name:  Richard & Rajan
Class: CSCI-6630
Lab:   Pi - Estimator
Date:  2026-10-21
Desc:  Parallel Search

*/

#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include <time.h>

// Thread arguments
typedef struct {
    long start;
    long count;
    long inside;
    unsigned int seed;
    int *results;
    double *x;
    double *y;
} ThreadData;

// Check if point is inside circle of radius 1
int insideCircle(double x, double y) {
    return (x * x + y * y <= 1.0);
}

// Thread worker
void *runTests(void *arg) {
    ThreadData *data = (ThreadData *)arg;

    data->inside = 0;

    for (long i = data->start; i < data->start + data->count; i++) {

        double x = (double)rand_r(&data->seed) / RAND_MAX * 2.0 - 1.0;
        double y = (double)rand_r(&data->seed) / RAND_MAX * 2.0 - 1.0;

        int inside = insideCircle(x, y);

        data->x[i] = x;
        data->y[i] = y;
        data->results[i] = inside;

        data->inside += inside;
    }

    return NULL;
}

int main(int argc, char *argv[]) {

    if (argc != 3) {
        printf("Usage: %s <threads> <tests>\n", argv[0]);
        return 1;
    }

    int numThreads = atoi(argv[1]);
    long numTests = atol(argv[2]);

    if (numThreads <= 0 || numTests <= 0) {
        printf("Threads and tests must be positive.\n");
        return 1;
    }

    pthread_t threads[numThreads];
    ThreadData data[numThreads];

    double *x = malloc(numTests * sizeof(double));
    double *y = malloc(numTests * sizeof(double));
    int *results = malloc(numTests * sizeof(int));

    if (!x || !y || !results) {
        printf("Memory allocation failed.\n");
        free(x);
        free(y);
        free(results);
        return 1;
    }

    long testsPerThread = numTests / numThreads;
    long remainder = numTests % numThreads;
    long start = 0;

    // Start threads
    for (int i = 0; i < numThreads; i++) {

        data[i].start = start;
        data[i].count = testsPerThread + (i < remainder ? 1 : 0);
        data[i].seed = (unsigned int)time(NULL) ^ (unsigned int)(i * 1234567U + 1U);
        data[i].x = x;
        data[i].y = y;
        data[i].results = results;

        pthread_create(&threads[i], NULL, runTests, &data[i]);

        start += data[i].count;
    }

    // Wait for threads
    long totalInside = 0;

    for (int i = 0; i < numThreads; i++) {
        pthread_join(threads[i], NULL);
        totalInside += data[i].inside;
    }

    // Estimate Pi
    double pi = 4.0 * totalInside / numTests;

    // Write CSV
    char filename[100];
    snprintf(filename, sizeof(filename), "results_%ld.csv", numTests);

    FILE *file = fopen(filename, "w");

    if (!file) {
        perror("Failed to open CSV");
        free(x);
        free(y);
        free(results);
        return 1;
    }

    fprintf(file, "x,y,inside\n");

    for (long i = 0; i < numTests; i++) {
        fprintf(file, "%.6f,%.6f,%s\n",
                x[i], y[i],
                results[i] ? "true" : "false");
    }

    fclose(file);

    printf("Threads: %d\n", numThreads);
    printf("Tests:   %ld\n", numTests);
    printf("Inside:  %ld\n", totalInside);
    printf("Pi:      %.8f\n", pi);
    printf("File:    %s\n", filename);

    free(x);
    free(y);
    free(results);

    return 0;
}
