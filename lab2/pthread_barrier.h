#ifndef PTHREAD_BARRIER_H
#define PTHREAD_BARRIER_H

#include <pthread.h>
#include <errno.h>

#ifdef __APPLE__

#define PTHREAD_BARRIER_SERIAL_THREAD 1

typedef int pthread_barrierattr_t;

typedef struct {
    pthread_mutex_t mutex;
    pthread_cond_t cond;
    unsigned int limit;
    unsigned int count;
    unsigned int phase;
} pthread_barrier_t;

static inline int pthread_barrier_init(pthread_barrier_t *barrier, const pthread_barrierattr_t *attr, unsigned int count) {
    if (count == 0) return EINVAL;
    pthread_mutex_init(&barrier->mutex, NULL);
    pthread_cond_init(&barrier->cond, NULL);
    barrier->limit = count;
    barrier->count = 0;
    barrier->phase = 0;
    return 0;
}

static inline int pthread_barrier_destroy(pthread_barrier_t *barrier) {
    pthread_mutex_destroy(&barrier->mutex);
    pthread_cond_destroy(&barrier->cond);
    return 0;
}

static inline int pthread_barrier_wait(pthread_barrier_t *barrier) {
    pthread_mutex_lock(&barrier->mutex);
    unsigned int phase = barrier->phase;
    barrier->count++;
    
    if (barrier->count >= barrier->limit) {
        barrier->phase++;
        barrier->count = 0;
        pthread_cond_broadcast(&barrier->cond);
        pthread_mutex_unlock(&barrier->mutex);
        return PTHREAD_BARRIER_SERIAL_THREAD;
    } else {
        while (phase == barrier->phase) {
            pthread_cond_wait(&barrier->cond, &barrier->mutex);
        }
        pthread_mutex_unlock(&barrier->mutex);
        return 0;
    }
}

#endif // __APPLE__
#endif // PTHREAD_BARRIER_H
