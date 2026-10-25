
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

// Shared progress across threads
typedef struct {
    pthread_mutex_t mutex;
    long completed;
    long inside;
    long nextLog;
    long logEvery;
    long lastLogged;
    FILE *file;
} Progress;

// Thread arguments
typedef struct {
    long start;
    long count;
    long inside;
    unsigned int seed;
    int *results;
    double *x;
    double *y;
    Progress *progress;
} ThreadData;

// Check if point is inside circle of radius 1
int insideCircle(double x, double y) {
    return (x * x + y * y <= 1.0);
}

// Update shared progress
void updateProgress(Progress *p, long count, long inside) {
    pthread_mutex_lock(&p->mutex);

    p->completed += count;
    p->inside += inside;

    if (p->completed >= p->nextLog) {
        double pi = 4.0 * p->inside / p->completed;

        fprintf(p->file, "%ld,%.8f\n", p->completed, pi);
        fflush(p->file);

        p->lastLogged = p->completed;
        p->nextLog = p->completed + p->logEvery;
    }

    pthread_mutex_unlock(&p->mutex);
}

// Thread worker
void *runTests(void *arg) {
    ThreadData *data = (ThreadData *)arg;

    data->inside = 0;

    long batchCount = 0;
    long batchInside = 0;

    long batchSize = data->progress->logEvery / 4;
    if (batchSize < 1) batchSize = 1;
    if (batchSize > 10000) batchSize = 10000;

    for (long i = data->start; i < data->start + data->count; i++) {

        double x = (double)rand_r(&data->seed) / RAND_MAX * 2.0 - 1.0;
        double y = (double)rand_r(&data->seed) / RAND_MAX * 2.0 - 1.0;

        int inside = insideCircle(x, y);

        data->x[i] = x;
        data->y[i] = y;
        data->results[i] = inside;

        data->inside += inside;
        batchInside += inside;
        batchCount++;

        // Periodically update global progress
        if (batchCount >= batchSize) {
            updateProgress(data->progress, batchCount, batchInside);

            batchCount = 0;
            batchInside = 0;
        }
    }

    // Include remaining tests
    if (batchCount > 0) {
        updateProgress(data->progress, batchCount, batchInside);
    }

    return NULL;
}

int main(int argc, char *argv[]) {

    if (argc < 3 || argc > 4) {
        printf("Usage: %s <threads> <tests> [logEvery]\n", argv[0]);
        return 1;
    }

    int numThreads = atoi(argv[1]);
    long numTests = atol(argv[2]);

    if (numThreads <= 0 || numTests <= 0) {
        printf("Threads and tests must be positive.\n");
        return 1;
    }

    // Default: approximately 1000 progress samples
    long logEvery = numTests / 1000;
    if (logEvery < 1) logEvery = 1;

    if (argc == 4) {
        logEvery = atol(argv[3]);

        if (logEvery <= 0) {
            printf("Log interval must be positive.\n");
            return 1;
        }
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

    // Open Pi progress file
    char piFilename[100];
    snprintf(piFilename, sizeof(piFilename), "pi_%ld.csv", numTests);

    FILE *piFile = fopen(piFilename, "w");

    if (!piFile) {
        perror("Failed to open Pi CSV");
        free(x);
        free(y);
        free(results);
        return 1;
    }

    fprintf(piFile, "count,pi\n");

    Progress progress = {
        .mutex = PTHREAD_MUTEX_INITIALIZER,
        .completed = 0,
        .inside = 0,
        .nextLog = logEvery,
        .logEvery = logEvery,
        .lastLogged = 0,
        .file = piFile
    };

    long testsPerThread = numTests / numThreads;
    long remainder = numTests % numThreads;
    long start = 0;

    // Start threads
    int started = 0;

    for (int i = 0; i < numThreads; i++) {

        data[i].start = start;
        data[i].count = testsPerThread + (i < remainder ? 1 : 0);
        data[i].seed = (unsigned int)time(NULL) ^
                       (unsigned int)(i * 1234567U + 1U);
        data[i].x = x;
        data[i].y = y;
        data[i].results = results;
        data[i].progress = &progress;
        data[i].inside = 0;

        if (pthread_create(&threads[i], NULL, runTests, &data[i]) != 0) {
            fprintf(stderr, "Failed to create thread %d\n", i);
            break;
        }

        started++;
        start += data[i].count;
    }

    // Wait for threads
    for (int i = 0; i < started; i++) {
        pthread_join(threads[i], NULL);
    }

    if (started != numThreads) {
        fclose(piFile);
        pthread_mutex_destroy(&progress.mutex);
        free(x);
        free(y);
        free(results);
        return 1;
    }

    long totalInside = progress.inside;

    // Final Pi estimate
    double pi = 4.0 * totalInside / numTests;

    // Ensure final count is logged
    if (progress.lastLogged != numTests) {
        fprintf(piFile, "%ld,%.8f\n", numTests, pi);
    }

    fclose(piFile);
    pthread_mutex_destroy(&progress.mutex);

    // Write outside-circle points only
    char filename[100];
    snprintf(filename, sizeof(filename), "results_%ld.csv", numTests);

    FILE *file = fopen(filename, "w");

    if (!file) {
        perror("Failed to open results CSV");
        free(x);
        free(y);
        free(results);
        return 1;
    }

    fprintf(file, "count,x,y\n");

    long outsideCount = 0;

    for (long i = 0; i < numTests; i++) {
        if (!results[i]) {
            fprintf(file, "%ld,%.6f,%.6f\n", i + 1, x[i], y[i]);
            outsideCount++;
        }
    }

    fclose(file);

    printf("Threads: %d\n", numThreads);
    printf("Tests:   %ld\n", numTests);
    printf("Inside:  %ld\n", totalInside);
    printf("Outside: %ld\n", outsideCount);
    printf("Pi:      %.8f\n", pi);
    printf("Error:   %.8f\n", pi - 3.141592653589793);
    printf("Points:  %s\n", filename);
    printf("Pi Log:  %s\n", piFilename);

    free(x);
    free(y);
    free(results);

    return 0;
}
