# Núcleo C99 da Légua. Build leve (-j1 por padrão): make test
CC      ?= gcc
CFLAGS  ?= -std=c99 -O1 -g -Wall -Wextra -Wpedantic -Werror -Wshadow -Wconversion -Iinclude
BUILD   := build
SRC     := src/frame.c src/toa.c src/endpoint.c
OBJ     := $(SRC:src/%.c=$(BUILD)/%.o)
TESTS   := $(BUILD)/test_codec $(BUILD)/test_sim $(BUILD)/toa_table
VECTORS := tests/vectors/frames.txt

.PHONY: all test clean vectors
all: $(TESTS)

$(BUILD)/%.o: src/%.c include/legua/legua.h | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/%: tests/%.c $(OBJ) tests/testenv.h | $(BUILD)
	$(CC) $(CFLAGS) $< $(OBJ) -o $@

$(BUILD):
	mkdir -p $(BUILD)

test: $(TESTS)
	$(BUILD)/test_codec $(VECTORS)
	$(BUILD)/test_sim

vectors:
	cd .. && PYTHONPATH=. python3 -m simsuite.protocol.wire --vetores core/$(VECTORS)

clean:
	rm -rf $(BUILD)
