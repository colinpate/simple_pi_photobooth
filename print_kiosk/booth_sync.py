import subprocess
import threading
import time
import os
import glob

WATCHDOG_TIMEOUT = 10
CHECK_INTERVAL_S = 3
RSYNC_TIMEOUT = 300

class BoothSync:
    def __init__(self, mount_addresses, mount_source, remote_photo_dir, photo_dir, print_subdirs, **kwargs):
        self.stop_thread = False
        self._is_nfs_mounted = False
        self.mount_addresses = mount_addresses
        self.mount_source = mount_source
        self.remote_photo_dir = remote_photo_dir
        self.photo_dir = photo_dir
        self.print_subdirs = print_subdirs
        self.mount_check_thread = threading.Thread(target=self.check_nfs_mount)
        self.mount_check_thread.start()
        self.update_watchdog()
        self._is_syncing = False
        
    def update_watchdog(self):
        self.watchdog_updated = time.time()
        if not self.mount_check_thread.is_alive():
            raise ValueError("Mount check thread failed!")
            
    def is_syncing(self):
        return self._is_syncing
        
    def check_nfs_mount(self):
        while not self.stop_thread:
            ls_timeout = False
            
            try:
                # Check if the mount point is available by listing its contents
                subprocess.check_output(['ls', os.path.join(self.remote_photo_dir, self.print_subdirs[0])], timeout=1)
                self._is_nfs_mounted = True
            except (subprocess.CalledProcessError) as exception:
                print("NFS ls failed")
                self._is_nfs_mounted = False
            except (subprocess.TimeoutExpired) as exception:
                print("NFS ls timed out")
                self._is_nfs_mounted = False
                ls_timeout = True
                
            if self._is_nfs_mounted:
                self._is_syncing = True
                self.sync_remote_to_local(self.photo_dir, timeout=RSYNC_TIMEOUT)
                self._is_syncing = False
                self.get_thumbnails()
                
            # Unmount the directory if ls times out, cuz it can get stuck
            if ls_timeout:
                try:
                    subprocess.check_output(['sudo', "umount", "-f", self.remote_photo_dir], timeout=3)
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exception:
                    print("Umount failed", exception)
                    
            if not self._is_nfs_mounted:
                for mount_address in self.mount_addresses:
                    try:
                        subprocess.check_output(['sudo', "mount", f"{mount_address}:{self.mount_source}", self.remote_photo_dir], timeout=3)
                        print("Successfully mounted from", mount_address)
                        break
                    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exception:
                        print("Failed to mount from", mount_address)
                        
            time.sleep(CHECK_INTERVAL_S)
            
            if (time.time() - self.watchdog_updated) > WATCHDOG_TIMEOUT:
                raise ValueError("Booth sync thread watchdog timed out")
            
    def is_nfs_mounted(self):
        return self._is_nfs_mounted
            
    def sync_remote_to_local(self, local_dir, timeout):
        try:
            # Attempt to sync the mounted directory
            subprocess.check_output(['rsync', "-a", self.remote_photo_dir, local_dir], timeout=timeout)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exception:
            print("rsync failed", exception)

    def shutdown(self):
        self.stop_thread = True
        self.mount_check_thread.join()

    def get_thumbnails(self):
        new_thumbnails = False

        photo_paths = []
        for subdir in self.print_subdirs:
            glob_str = f"{self.photo_dir}/{subdir}/*.jpg"
            photo_paths += glob.glob(glob_str)

        photo_paths_sorted = sorted(photo_paths)[::-1]

        print(photo_paths_sorted)



