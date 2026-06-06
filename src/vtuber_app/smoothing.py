import math
import time

class LowPassFilter:
    def __init__(self, alpha):
        self.alpha = alpha
        self.y = None

    def __call__(self, x):
        if self.y is None:
            self.y = x
        else:
            self.y = self.alpha * x + (1 - self.alpha) * self.y
        return self.y

class OneEuroFilter:
    def __init__(self, min_cutoff=1.0, beta=0.5, d_cutoff=1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.x_filter = LowPassFilter(self._alpha(min_cutoff))
        self.dx_filter = LowPassFilter(self._alpha(d_cutoff))
        self.last_time = None

    def _alpha(self, cutoff, dt=1.0):
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, x, timestamp=None):
        if timestamp is None:
            timestamp = time.time()
            
        if self.last_time is None:
            self.last_time = timestamp
            return x

        dt = timestamp - self.last_time
        if dt <= 0:
            return self.x_filter.y if self.x_filter.y is not None else x

        # Estimate derivative
        prev_x = self.x_filter.y if self.x_filter.y is not None else x
        dx = (x - prev_x) / dt
        edx = self.dx_filter(dx)
        
        # Compute cutoff frequency
        cutoff = self.min_cutoff + self.beta * abs(edx)
        alpha = self._alpha(cutoff, dt)
        
        self.last_time = timestamp
        return self.x_filter(x) # Note: x_filter alpha needs to be updated

    # Correcting the __call__ to update alpha correctly
    def update(self, x, timestamp=None):
        if timestamp is None:
            timestamp = time.time()
            
        if self.last_time is None:
            self.last_time = timestamp
            return x

        dt = timestamp - self.last_time
        if dt <= 0:
            return self.x_filter.y if self.x_filter.y is not None else x

        # Update dx filter
        prev_x = self.x_filter.y if self.x_filter.y is not None else x
        dx = (x - prev_x) / dt
        self.dx_filter.alpha = self._alpha(self.d_cutoff, dt)
        edx = self.dx_filter(dx)
        
        # Update x filter
        cutoff = self.min_cutoff + self.beta * abs(edx)
        self.x_filter.alpha = self._alpha(cutoff, dt)
        result = self.x_filter(x)
        
        self.last_time = timestamp
        return result

class MultiOneEuroFilter:
    def __init__(self, num_elements, min_cutoff=1.0, beta=0.5, d_cutoff=1.0):
        self.filters = [OneEuroFilter(min_cutoff, beta, d_cutoff) for _ in range(num_elements)]

    def __call__(self, x_list, timestamp=None):
        return [f.update(x, timestamp) for f, x in zip(self.filters, x_list)]
