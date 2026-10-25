
CC = cc
CFLAGS = -O2 -Wall -Wextra -pthread

TARGET = main
THREADS ?= 4
TESTS ?= 100000

.PHONY: all run clean

# Compile
all: $(TARGET)

$(TARGET): main.c
	$(CC) $(CFLAGS) -o $(TARGET) main.c

# Run
run: $(TARGET)
	./$(TARGET) $(THREADS) $(TESTS)

# Clean
clean:
	rm -f $(TARGET)
