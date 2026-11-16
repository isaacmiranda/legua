# Núcleo C99 da Légua. Build leve (-j1 por padrão): make test
CC      ?= gcc
CFLAGS  ?= -std=c99 -O1 -g -Wall -Wextra -Wpedantic -Werror -Wshadow -Wconversion -Iinclude
BUILD   := build
SRC     := src/frame.c src/toa.c src/endpoint.c
OBJ     := $(SRC:src/%.c=$(BUILD)/%.o)
TESTS   := $(BUILD)/test_codec $(BUILD)/test_sim $(BUILD)/toa_table
SHIM    := $(BUILD)/liblegua_shim.so
VECTORS := tests/vectors/frames.txt

.PHONY: all test clean vectors fuzz
all: $(TESTS) $(SHIM)

# Biblioteca de teste para o Python (teste de equivalência com endpoint.py); não faz parte do núcleo
$(SHIM): tests/pyshim.c $(SRC) include/legua/legua.h tests/testenv.h | $(BUILD)
	$(CC) $(CFLAGS) -shared -fPIC -Wno-unused-function tests/pyshim.c $(SRC) -o $@

$(BUILD)/%.o: src/%.c include/legua/legua.h | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/%: tests/%.c $(OBJ) tests/testenv.h | $(BUILD)
	$(CC) $(CFLAGS) $< $(OBJ) -o $@

$(BUILD):
	mkdir -p $(BUILD)

# Robustez com sanitizadores (ASan + UBSan); ~1 min. Não entra em `make test`.
fuzz: tests/test_fuzz.c $(SRC) include/legua/legua.h tests/testenv.h profiles/br2026.h | $(BUILD)
	$(CC) $(CFLAGS) -O1 -fsanitize=address,undefined -fno-sanitize-recover=undefined tests/test_fuzz.c $(SRC) -o $(BUILD)/test_fuzz_asan
	$(BUILD)/test_fuzz_asan

test: $(TESTS) $(SHIM)
	$(BUILD)/test_codec $(VECTORS)
	$(BUILD)/test_sim

vectors:
	cd .. && PYTHONPATH=. python3 -m simsuite.protocol.wire --vetores core/$(VECTORS)
	cd .. && PYTHONPATH=. python3 tools/gen_modetab.py

clean:
	rm -rf $(BUILD)
