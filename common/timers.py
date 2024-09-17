import time

class Timers:
    def __init__(self):
        self.end_times = {}
        self.durations = {}
        self.update_time()
        
    def update_time(self):
        self._now = time.perf_counter()
        
    def setup(self, timer, duration):
        self.durations[timer] = duration
        
    def start(self, timer, duration=None):
        if duration is not None:
            self.durations[timer] = duration
            timer_duration = duration
        else:
            try:
                timer_duration = self.durations[timer]
            except KeyError:
                raise ValueError(f"Timer duration not set for {timer}")
        end_time = self._now + timer_duration
        self.end_times[timer] = end_time
        
    def restart(self, timer):
        self.start(timer, duration=None)
        
    def time_left(self, timer):
        try:
            end_time = self.end_times[timer]
        except KeyError:
            raise ValueError(f"Timer never started {timer}")
        if end_time is not None:
            time_left = self.end_times[timer] - self._now
        else:
            time_left = None
        return time_left
        
    def check(self, timer, auto_restart=False, auto_stop=False):
        if self.time_left(timer) <= 0:
            if auto_restart:
                self.restart(timer)
            elif auto_stop:
                self.end_times[timer] = None
            return True
        else:
            return False
        
