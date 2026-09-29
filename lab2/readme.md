# Project Name: Lab 2

**Course:** CSCI-6330  
**Author:** Richard Hoehn  
**Date:** September 29th, 2026

---

## AI Disclosure & Academic Integrity Statement

**Important Notice for Grading:** Artificial intelligence tools were used as part of the development and troubleshooting process for this assignment.

### AI-Assisted Components

The custom `pthread_barrier_t` compatibility layer found in `pthread_barrier.h` was researched and generated with the assistance of **Gemini AI**.

- **Why it was used:** macOS does not provide native support for the POSIX `pthread_barrier_t` interface that is available on Linux. Gemini AI was used as a research assistant to develop a compatibility implementation using `pthread_mutex_t` and `pthread_cond_t`, allowing the program to compile and run on macOS.
- **Additional AI assistance:** AI tools were also used for debugging, code review, formatting guidance, pthread synchronization concepts, and development of the optional performance logging functionality.
- **Verification:** All AI-assisted code and recommendations were reviewed, tested, and integrated by Richard Hoehn.

---

## Project Description

This project implements the Hotplate Problem as a multi-threaded C application using the POSIX threads (`pthreads`) library.

The program divides the interior rows of the hotplate grid among multiple threads. Each thread calculates a portion of the next grid state, while barriers are used to synchronize the threads between stages of each iteration.

The implementation demonstrates:

- POSIX thread creation and management
- Distribution of work across multiple threads
- Barrier synchronization
- Shared-memory parallel processing
- Race-condition prevention
- Iterative convergence
- Performance measurement
- Optional CSV performance logging

The original/main thread participates in the computation as thread 0 while also handling program output.

---

## Compilation & Execution

### Prerequisites

The project can be compiled on:

- **macOS** using Clang / Xcode Command Line Tools
- **Linux** using GCC, Clang, or another compatible C compiler

The included `pthread_barrier.h` provides a compatibility implementation for macOS. Linux systems use their native POSIX pthread barrier implementation.

### How to Compile

A portable compilation command is:

```bash
cc -pthread -o l2 l2.c
```

On macOS, this will typically use Clang.

You may also compile explicitly with Clang:

```bash
clang -pthread -o l2 l2.c
```

Or on Linux with GCC:

```bash
gcc -pthread -o l2 l2.c
```

The included `Makefile` can also be used:

```bash
make
```

---

## How to Run

The program requires eight command-line arguments:

```text
./l2 rows cols top left right bottom epsilon num_threads
```

Example:

```bash
./l2 500 600 100 100 100 400 0.01 8
```

The final argument specifies the total number of threads used by the program, including the original/main thread.

For example:

```text
8
```

means the program uses eight total threads:

- 1 original/main thread
- 7 additional pthread workers

---

## Optional Performance Logging

An optional ninth argument can be provided to specify a CSV results file:

```text
./l2 rows cols top left right bottom epsilon num_threads results_file
```

Example:

```bash
./l2 500 600 100 100 100 400 0.01 8 results.csv
```

If no results filename is provided, the program runs normally without writing performance data to a file.

If a filename is provided, the program appends the operating system, number of threads, and execution time to the CSV file.

Example output:

```csv
os,num_threads,time
Apple,1,2.429499
Apple,2,1.312445
Apple,4,0.745221
Apple,8,0.512338
```

On Linux, the operating system field is recorded as:

```text
Linux
```

On macOS, it is recorded as:

```text
Apple
```

This allows performance results from different systems to be compared in the same CSV format.

---

## Performance Timing

The program uses `gettimeofday()` to measure the amount of time spent performing the iterative hotplate calculation.

Initialization and thread creation are completed before the timer begins.

The program reports the execution time using the following format:

```text
TOTAL TIME 2.429499
```

When CSV logging is enabled, this same execution time is written to the results file.

---

## Running Performance Tests

The supplied `l2.sh` script can be used to compile the program and run a series of tests using different thread counts. The resulting CSV file can then be used to plot execution time versus the number of threads.

---

## Thread Synchronization

Each worker thread is assigned a range of interior grid rows.

During each iteration:

1. Each thread calculates its assigned portion of `gridNext`.
2. A barrier ensures that all threads finish their calculations.
3. Thread 0 determines the global maximum difference.
4. A barrier ensures that the convergence result is available to all threads.
5. Each thread copies its assigned rows from `gridNext` into `gridCurr`.
6. A barrier ensures that the current grid is completely updated before the next iteration begins.
7. The threads synchronize before starting the next iteration.

This prevents one thread from beginning a new iteration while another thread is still modifying data from the previous iteration.

---

## File Structure

```text
lab2/
├── l2.c
├── pthread_barrier.h
├── Makefile
├── l2.sh
├── .clang-format
└── results.csv
```

### Files

- `l2.c` — Main program containing the hotplate algorithm, pthread worker function, synchronization logic, timing, and optional CSV logging.
- `pthread_barrier.h` — Compatibility implementation of POSIX barriers for macOS.
- `Makefile` — Builds the `l2` executable and provides clean/run targets.
- `l2.sh` — Runs multiple performance tests using different thread counts.
- `.clang-format` — Defines the source-code formatting style used by the project.
- `res_01.csv & res_02.txt` — Optional generated performance-results file. This file is only created when a filename is supplied to the program.

---

## Example

Compile:

```bash
make
```

Run without logging:

```bash
./l2 500 600 100 100 100 400 0.01 8
```

Run with logging:

```bash
./l2 500 600 100 100 100 400 0.01 8 results.csv
```

Run the automated performance tests:

```bash
./l2.sh
```

Clean the compiled executable:

```bash
make clean
```
