#### Seeting for the Kalman filter that smooths the data and provides a fixed speed predator detection
process_freq = 40  # frequency of process in Hz
process_noise_var = 12  # variance of process noise
measurement_noise_var = 0.00075  # variance of measurement noise (in simulation space 20 x 20)
max_timesteps_without_detection = 50  # maximum number of timesteps without detection before the predator is considered lost