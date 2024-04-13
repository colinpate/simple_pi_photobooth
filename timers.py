import time

class Timers:
    def __init__(self):
        self.end_times = {}
        self.durations = {}
        
    def start(self, timer, duration):
        now = time.perf_counter()
        end_time = now + duration
        self.end_times[timer] = end_time
        self.durations[timer] = duration
        
    def restart(self, timer):
        self.start(timer, duration=self.durations[timer])
        
    def time_left(self, timer):
        now = time.perf_counter()
        return self.end_times[timer] - now
        
    def check(self, timer, auto_restart=False):
        if self.time_left(timer) <= 0:
            if auto_restart:
                self.restart(timer)
            return True
        else:
            return False
        
