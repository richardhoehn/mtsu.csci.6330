/*

Name:  Richard Hoehn
Class: CSCI-6630
Lab:   01
Date:  2026-09-02
Desc:  Hotplate Problem

*/

// Setup Inclddes & Libs
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>

// Functions
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


// Start Program
int main(int argc, char* argv[]){
    // Setup Constants
    const int argCount = 7;

    // Setup Vars
    int nRows;
    int nCols;
    float initTop;
    float initBottom;
    float initLeft;
    float initRight;
    float epsilon;

    // Lcoal Vars
    float diff = 0.0f;
    int itr = 0;


    // Make Sure I got The corrent count of Parameters
    if(argc != (argCount+1)){
        printf("\n");
        printf("*** Missing Correct Argument Count of %d! ***\n", argCount);
        printf("\n");
        return -1;
    }

    // Get Args - Index based
    nRows = atoi(argv[1]); // Convert to an Integer
    nCols = atoi(argv[2]); // Convert to an Integer
    initTop = atof(argv[3]);
    initLeft= atof(argv[4]);
    initRight = atof(argv[5]);
    initBottom = atof(argv[6]);
    epsilon = atof(argv[7]);

    // Setup Grid
    float **gridNext = (float **)malloc(nRows * sizeof(float *));
    float **gridCurr = (float **)malloc(nRows * sizeof(float *));
    for (int i = 0; i < nRows; i++) {
        gridNext[i] = (float *)malloc(nCols * sizeof(float));
        gridCurr[i] = (float *)malloc(nCols * sizeof(float));
    }

    // Setup Walls: Top 
    for (int i = 0; i < nCols; i++) { gridCurr[0][i] = initTop; } // Top
    for (int i = 0; i < nRows; i++) { gridCurr[i][0] = initLeft; } // Left 
    for (int i = 0; i < nRows; i++) { gridCurr[i][nCols-1] = initRight; } // Right
    for (int i = 0; i < nCols; i++) { gridCurr[nRows-1][i] = initBottom; } // Bottom 

    // Get Edge Sum
    float edgeSum = 0.0f;
    float edgeAvg = 0.0f;
    for (int i = 0; i < nCols; i++) {
        edgeSum += gridCurr[0][i];
        edgeSum += gridCurr[nRows-1][i];
    }
    for (int i = 1; i < nRows - 1; i++) {
        edgeSum += gridCurr[i][0];
        edgeSum += gridCurr[i][nCols-1];
    }   
    edgeAvg = edgeSum / (2 * nRows + 2 * nCols - 4);

    // Set Interior to Edge Average
    for (int i = 1; i < nRows - 1; i++) {
        for (int j = 1; j < nCols - 1; j++) {
            gridCurr[i][j] = edgeAvg;
        }
    }

    // Copy current grid into next grid
    copyGrid(gridCurr, gridNext, nRows, nCols);

    do {
        diff = 0.0f;

        for (int i = 1; i < nRows - 1; i++) {
            for (int j = 1; j < nCols - 1; j++) {

                gridNext[i][j] =
                    (gridCurr[i-1][j] +
                    gridCurr[i+1][j] +
                    gridCurr[i][j-1] +
                    gridCurr[i][j+1]) / 4.0f;

                float delta = fabsf(gridNext[i][j] - gridCurr[i][j]);

                if (delta > diff) {
                    diff = delta;
                }
            }
        }

        // Copy next grid into current grid
        copyGrid(gridNext, gridCurr, nRows, nCols);

        // Print powers of 2
        if (isPowerOfTwo(itr)) {
            printStatus(itr, diff);
        }

        // Stop if converged
        if (diff < epsilon) {
            break;
        }

        itr++;

    } while (1);

    printStatus(itr, diff);

    return 0;
}
