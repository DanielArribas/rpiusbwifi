#!/usr/bin/python3
import time
import os
import subprocess
import logging
from watchdog.observers import Observer
from watchdog.events import *

# Set up logging
logging.basicConfig(level=logging.DEBUG)  # Set to logging.INFO to reduce verbosity
logger = logging.getLogger(__name__)

CMD_MOUNT = "sudo /sbin/modprobe g_mass_storage file=/piusb.bin stall=0 removable=1"
CMD_UNMOUNT = "sudo /sbin/modprobe g_mass_storage -r"
CMD_SYNC = "sync"
CMD_REMOUNT_FS = "sudo umount /mnt/usb_share && sudo mount /mnt/usb_share"

WATCH_PATH = "/mnt/usb_share"
ACT_EVENTS = [DirDeletedEvent, DirMovedEvent, FileDeletedEvent, FileModifiedEvent, FileMovedEvent]
ACT_TIME_OUT = 5   # Time to wait after Samba changes
PERIODIC_REFRESH = 30  # Refresh filesystem every 30 seconds to catch USB changes

class DirtyHandler(FileSystemEventHandler):
    def __init__(self):
        self.reset()
        logger.debug("DirtyHandler initialized.")

    def on_any_event(self, event):
        if type(event) in ACT_EVENTS:
            self._dirty = True
            self._dirty_time = time.time()
            logger.debug(f"Event detected: {event}. Marking as dirty.")

    @property
    def dirty(self):
        return self._dirty

    def dirty_time(self):
        return self._dirty_time

    def reset(self):
        self._dirty = False
        self._dirty_time = 0
        self._path = None
        logger.debug("DirtyHandler reset.")

def run_command(command):
    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        logger.debug(f"Output of {command}: {result.stdout}")
        if result.stderr:
            logger.debug(f"Error of {command}: {result.stderr}")
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        logger.error(f"Error executing {command}: {e}")
        return False

def remount_filesystem():
    """Remount the filesystem to pick up changes made via USB"""
    logger.debug("Remounting filesystem to pick up USB changes...")
    success = run_command(CMD_REMOUNT_FS)
    if success:
        logger.debug("Filesystem remounted successfully.")
    else:
        logger.error("Failed to remount filesystem.")
    return success

# Unmount & Mount the device
logger.debug("Unmounting the device.")
run_command(CMD_UNMOUNT)
logger.debug("Mounting the device.")
run_command(CMD_MOUNT)

evh = DirtyHandler()
observer = Observer()
observer.schedule(evh, path=WATCH_PATH, recursive=True)
observer.start()
logger.debug("Observer started to monitor the path.")

last_refresh_time = time.time()

try:
    while True:
        current_time = time.time()
        
        # Periodic refresh to catch USB changes
        if current_time - last_refresh_time >= PERIODIC_REFRESH:
            logger.debug("Performing periodic filesystem refresh...")
            remount_filesystem()
            last_refresh_time = current_time
        
        # Handle Samba-side changes (original logic)
        if evh.dirty:
            time_out = time.time() - evh.dirty_time()
            logger.debug(f"Samba change detected. Timeout: {time_out}s.")

            if time_out >= ACT_TIME_OUT:
                logger.debug("Timeout exceeded. Unmounting USB device.")
                run_command(CMD_UNMOUNT)
                time.sleep(1)
                logger.debug("Syncing after unmounting.")
                run_command(CMD_SYNC)
                time.sleep(2000)
                logger.debug("Remounting USB device.")
                run_command(CMD_MOUNT)
                evh.reset()
                
                # Reset refresh timer since we just did a full cycle
                last_refresh_time = current_time

        time.sleep(1)

except KeyboardInterrupt:
    logger.debug("KeyboardInterrupt received. Stopping observer.")
    observer.stop()
    observer.join()
    logger.debug("Observer stopped and joined.")
