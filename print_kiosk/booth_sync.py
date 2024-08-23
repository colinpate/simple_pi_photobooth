import subprocess
import threading
import time


class BoothSync:
    def __init__(self, mount_addresses, mount_source, remote_photo_dir, **kwargs):
        self.stop_thread = False
        self._is_nfs_mounted = False
        self.mount_addresses = mount_addresses
        self.mount_source = mount_source
        self.remote_photo_dir = remote_photo_dir
        self.mount_check_thread = threading.Thread(target=self.check_nfs_mount)
        self.mount_check_thread.start()
        
    def check_nfs_mount(self):
        while not self.stop_thread:
            ls_timeout = False
            
            try:
                # Check if the mount point is available by listing its contents
                subprocess.check_output(['ls', self.remote_photo_dir + "/color"], timeout=1)
                self._is_nfs_mounted = True
            except (subprocess.CalledProcessError) as exception:
                print("NFS ls failed")
                self._is_nfs_mounted = False
            except (subprocess.TimeoutExpired) as exception:
                print("NFS ls timed out")
                self._is_nfs_mounted = False
                ls_timeout = True
                
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
                        
            time.sleep(3)
            
    def is_nfs_mounted(self):
        return self._is_nfs_mounted
            
    def sync_remote_to_local(self, local_dir):
        try:
            # Attempt to sync the mounted directory
            subprocess.check_output(['rsync', "-a", self.remote_photo_dir, local_dir], timeout=5)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exception:
            print("rsync failed", exception)

    def shutdown(self):
        self.stop_thread = True
        self.mount_check_thread.join()
