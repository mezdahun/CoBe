import os

#### Seeting for the Kalman filter that smooths the data and provides a fixed speed predator detection
process_freq = 30  # frequency of process in Hz
process_noise_var = float(os.environ.get("KALMAN_PROCESS_VAR", 12))  # variance of process noise (stick-12, thymio-0.1)
measurement_noise_var = float(os.environ.get("KALMAN_MEAS_VAR", 0.075))  # variance of measurement noise (in simulation space 20 x 20) (stick-0.0075, thymio-0.0001)
max_timesteps_without_detection = 50  # maximum number of timesteps without detection before the predator is considered lost