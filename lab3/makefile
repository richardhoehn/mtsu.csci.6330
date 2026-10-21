
# Operating system
OS := $(shell uname -s)

# Compiler
ifeq ($(OS),Darwin)
    CC = $(shell brew --prefix llvm)/bin/clang
else
    CC = gcc
endif

# Settings
TARGET = l3
SRC = l3.c
OBJ = evalfunc.o
CFLAGS = -std=c11 -O2 -Wall -Wextra -fopenmp

# Runtime arguments
T ?= 8
N ?= 10

# Default build
all: $(TARGET)

# Compile evalfunc.c (if source is available)
evalfunc.o: evalfunc.c
	$(CC) $(CFLAGS) -c evalfunc.c -o evalfunc.o

# Build executable
$(TARGET): $(SRC) $(OBJ)
	$(CC) $(CFLAGS) $(SRC) $(OBJ) -o $(TARGET)

# Run
run: $(TARGET)
	./$(TARGET) $(T) $(N)

# Clean
clean:
	rm -f $(TARGET) $(OBJ)

.PHONY: all run clean
