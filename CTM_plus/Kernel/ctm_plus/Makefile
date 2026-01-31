# SPDX-License-Identifier: GPL-2.0
#
# CTM+ Kernel Module Makefile
#
# Build:
#   make                    # Build against running kernel
#   make KDIR=/path/to/src  # Build against specific kernel source
#
# Install:
#   sudo make install
#   sudo modprobe ctm_plus tier0_pages=1000 tier1_pages=100000
#
# Clean:
#   make clean
#

obj-m := ctm_plus.o
ctm_plus-y := ctm_plus_core.o ctm_plus_module.o

# Kernel build directory (default: running kernel)
KDIR ?= /lib/modules/$(shell uname -r)/build
PWD := $(shell pwd)

# Compiler flags
ccflags-y := -DDEBUG -g -Wall -Werror

# Default target
all: modules

modules:
	$(MAKE) -C $(KDIR) M=$(PWD) modules

modules_install:
	$(MAKE) -C $(KDIR) M=$(PWD) modules_install

clean:
	$(MAKE) -C $(KDIR) M=$(PWD) clean
	rm -f Module.symvers modules.order

# Install module and update module dependencies
install: modules_install
	depmod -a

# Load module with default parameters
load:
	sudo insmod ctm_plus.ko tier0_pages=1000 tier1_pages=100000

# Unload module
unload:
	sudo rmmod ctm_plus

# Reload module (unload + load)
reload: unload load

# Show module info
info:
	modinfo ctm_plus.ko

# Show kernel log for CTM+
log:
	dmesg | grep -i ctm

# Check sysfs interface
sysfs:
	@echo "=== CTM+ sysfs interface ==="
	@if [ -d /sys/kernel/ctm_plus ]; then \
		cat /sys/kernel/ctm_plus/stats; \
	else \
		echo "Module not loaded"; \
	fi

# Run checkpatch on source files
checkpatch:
	$(KDIR)/scripts/checkpatch.pl --no-tree -f *.c *.h

.PHONY: all modules modules_install clean install load unload reload info log sysfs checkpatch
