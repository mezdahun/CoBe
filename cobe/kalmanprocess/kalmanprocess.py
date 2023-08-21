"""Kalman filtering od values to provide a smoother predator trajectory"""

import numpy as np
import logging
# from filterpy.kalman import KalmanFilter
from scipy.linalg import block_diag
from filterpy.common import Q_discrete_white_noise

from cobe.pmodule.pmodule import generate_pred_json
from cobe.settings import logs

# Setting up file logger
logging.basicConfig(level=logs.log_level, format=logs.log_format)
logger = logs.setup_logger("cobe-kalmanproc")

from datetime import datetime
from queue import Empty
from cobe.settings import kalmanprocess as klmp


class KalmanFilter(object):
    def __init__(self, dt, u_x,u_y, std_acc, x_std_meas, y_std_meas):
        """
        :param dt: sampling time (time for 1 cycle)
        :param u_x: acceleration in x-direction
        :param u_y: acceleration in y-direction
        :param std_acc: process noise magnitude
        :param x_std_meas: standard deviation of the measurement in x-direction
        :param y_std_meas: standard deviation of the measurement in y-direction
        """

        # Define sampling time
        self.dt = dt

        # Define the  control input variables
        self.u = np.matrix([[u_x],[u_y]])

        # Intial State
        self.x = np.matrix([[0], [0], [0], [0]])

        # Define the State Transition Matrix A
        self.A = np.matrix([[1, 0, self.dt, 0],
                            [0, 1, 0, self.dt],
                            [0, 0, 1, 0],
                            [0, 0, 0, 1]])

        # Define the Control Input Matrix B
        self.B = np.matrix([[(self.dt**2)/2, 0],
                            [0,(self.dt**2)/2],
                            [self.dt,0],
                            [0,self.dt]])

        # Define Measurement Mapping Matrix
        self.H = np.matrix([[1, 0, 0, 0],
                            [0, 1, 0, 0]])

        #Initial Process Noise Covariance
        self.Q = np.matrix([[(self.dt**4)/4, 0, (self.dt**3)/2, 0],
                            [0, (self.dt**4)/4, 0, (self.dt**3)/2],
                            [(self.dt**3)/2, 0, self.dt**2, 0],
                            [0, (self.dt**3)/2, 0, self.dt**2]]) * std_acc**2

        #Initial Measurement Noise Covariance
        self.R = np.matrix([[x_std_meas**2,0],
                           [0, y_std_meas**2]])

        #Initial Covariance Matrix
        self.P = np.eye(self.A.shape[1])

    def predict(self):
        # Refer to :Eq.(9) and Eq.(10)  in https://machinelearningspace.com/object-tracking-simple-implementation-of-kalman-filter-in-python/?preview_id=1364&preview_nonce=52f6f1262e&preview=true&_thumbnail_id=1795

        # Update time state
        #x_k =Ax_(k-1) + Bu_(k-1)     Eq.(9)
        self.x = np.dot(self.A, self.x) + np.dot(self.B, self.u)

        # Calculate error covariance
        # P= A*P*A' + Q               Eq.(10)
        self.P = np.dot(np.dot(self.A, self.P), self.A.T) + self.Q
        return self.x[0:2]

    def update(self, z):

        # Refer to :Eq.(11), Eq.(12) and Eq.(13)  in https://machinelearningspace.com/object-tracking-simple-implementation-of-kalman-filter-in-python/?preview_id=1364&preview_nonce=52f6f1262e&preview=true&_thumbnail_id=1795
        # S = H*P*H'+R
        S = np.dot(self.H, np.dot(self.P, self.H.T)) + self.R

        # Calculate the Kalman Gain
        # K = P * H'* inv(H*P*H'+R)
        K = np.dot(np.dot(self.P, self.H.T), np.linalg.inv(S))  #Eq.(11)

        self.x = np.round(self.x + np.dot(K, (z - np.dot(self.H, self.x))))   #Eq.(12)

        I = np.eye(self.H.shape[1])

        # Update error covariance matrix
        self.P = (I - (K * self.H)) * self.P   #Eq.(13)
        return self.x[0:2]

def nearest_ind(items, pivot):
    logger.info("Finding nearest index to %s in %s", pivot, items)
    time_diff = np.abs([date - pivot for date in items])
    return time_diff.argmin(0), items[time_diff.argmin(0)]

def kalman_process_OD(od_position_queue, output_queue):
    """Main Kalman-filtering process running in separate thread, getting object detection values from the passed queue.
    The queue is filled by the object detection process, which is running in a separate thread. The elements pushed to the queue
    contain:
    - timestamp of capture
    - timestamp of pushing in queue
    - x, y coordinate of predator as tuple
    implementation according to: https://cocalc.com/share/public_paths/7557a5ac1c870f1ec8f01271959b16b49df9d087/08-Designing-Kalman-Filters.ipynb
    if output_queue is not None, the kalman process will push the predicted positions to the output queue otherwise writen to the pred.json file"""


    # Parameters
    process_freq = klmp.process_freq  # frequency of process in Hz
    process_noise_var = klmp.process_noise_var  # variance of process noise
    measurement_noise_var = klmp.process_noise_var  # variance of measurement noise (in simulation space 20 x 20)

    dt = 1 / process_freq  # time between process runs
    # initialize Kalman filter
    u_x = 0
    u_y = 0
    tracker = KalmanFilter(dt, u_x, u_y, process_noise_var, measurement_noise_var, measurement_noise_var) #KalmanFilter(dim_x=4, dim_z=2)

    t_last_predict = t_last_groundtruth = datetime.now()
    filter_parameters = {}

    while True:
        # try to get element from queue
        try:
            od_element = od_position_queue.get_nowait()
        except Empty:
            od_element = None

        if od_element is not None:
            (tcap_str, tpush, pred_positions) = od_element
            tcap = datetime.strptime(tcap_str, "%Y-%m-%d %H:%M:%S.%f")
            xod, yod = pred_positions[0]
            t_last_groundtruth = datetime.now()
            logger.debug(f"Kalman process: received element from queue: {od_element}")

        # check if time since last process run is greater than 1/process_freq
        if (datetime.now() - t_last_predict).total_seconds() > 1 / process_freq:
            # update tracker
            # check if we have a ground truth value since last prediction by comparing t_last_predict and t_last_groundtruth
            if (t_last_predict - t_last_groundtruth).total_seconds() >= 0:
                logger.debug(f"Kalman process: no ground truth value since last prediction, use prediction to further predict")
                (x, y) = tracker.predict()
                x = x[0, 0]
                y = y[0, 0]
                # (x1, y1) = tracker.update(np.array([[x], [y]]))
                # Saving filter parameters in the blind period until we get a new measurement from the past
                filter_parameters[datetime.now()] = [tracker.x, tracker.u, tracker.A, tracker.B, tracker.H, tracker.Q, tracker.R, tracker.P]
            else:
                logger.debug(f"Kalman process: found ground truth value since last prediction, use ground truth value to further predict")
                # # since there is a delay we predict as many times as we have to given dt and tcap of ground truth values
                # logger.info(f"tcap: {tcap}, now: {datetime.now()}")
                # Setting back filter to the closest state to the measurement time
                filter_params_ind, filter_params_key = nearest_ind(list(filter_parameters.keys()), tcap)
                filter_params = filter_parameters[filter_params_key]
                tracker.x = filter_params[0]
                tracker.u = filter_params[1]
                tracker.A = filter_params[2]
                tracker.B = filter_params[3]
                tracker.H = filter_params[4]
                tracker.Q = filter_params[5]
                tracker.R = filter_params[6]
                tracker.P = filter_params[7]
                (x, y) = tracker.predict()
                x = x[0, 0]
                y = y[0, 0]
                (x1, y1) = tracker.update(np.array([[xod], [yod]]))
                # The filter is now in the past and we predict until the current time
                time_diff = (tcap - datetime.now()).total_seconds()
                num_predictions = abs(int(time_diff * process_freq))
                logger.info(f"Time difference between tcap and now: {time_diff}, number of predictions: {num_predictions}")
                for i in range(num_predictions):
                    (x, y) = tracker.predict()
                    x = x[0, 0]
                    y = y[0, 0]
                    logger.info(f"Kalman process: predicted values: x: {x}, y: {y}")
                    # (x1, y1) = tracker.update(np.array([[x], [y]]))

                # Cleaning filter parameters from the past
                filter_parameters = {}
                filter_parameters[datetime.now()] = [tracker.x, tracker.u, tracker.A, tracker.B, tracker.H, tracker.Q,
                                                     tracker.R, tracker.P]

            t_last_predict = datetime.now()

            logger.debug(f"Kalman process: predicted values: x: {x}, y: {y}")

            # check if output queue is not None, if so push predicted values to output queue
            if output_queue is not None:
                logger.debug(f"Kalman process: output queue is not None, push predicted values to output queue")
                t_put = datetime.now()
                output_queue.put((t_put, [(x, y)]))
            else:
                # logger.info([(x, y)])
                generate_pred_json([(x, y)])

# def kalman_process_OD(od_position_queue, output_queue):
#     """Main Kalman-filtering process running in separate thread, getting object detection values from the passed queue.
#     The queue is filled by the object detection process, which is running in a separate thread. The elements pushed to the queue
#     contain:
#     - timestamp of capture
#     - timestamp of pushing in queue
#     - x, y coordinate of predator as tuple
#     implementation according to: https://cocalc.com/share/public_paths/7557a5ac1c870f1ec8f01271959b16b49df9d087/08-Designing-Kalman-Filters.ipynb
#     if output_queue is not None, the kalman process will push the predicted positions to the output queue otherwise writen to the pred.json file"""
#
#
#     # Parameters
#     process_freq = 30  # frequency of process in Hz
#     process_noise_var = 2  # variance of process noise
#     measurement_noise_var = 0.01  # variance of measurement noise (in simulation space 20 x 20)
#
#
#     dt = 1 / process_freq  # time between process runs
#     # initialize Kalman filter
#     tracker = KalmanFilter(dim_x=4, dim_z=2)
#
#
#     # state variables are [x, vx, y, vy]
#     # initialize state transition function
#     tracker.F = np.array([[1, dt, 0, 0],
#                           [0, 1, 0, 0],
#                           [0, 0, 1, dt],
#                           [0, 0, 0, 1]])
#
#     # assuming independent x and y noise for process noise matrix
#     q = Q_discrete_white_noise(dim=2, dt=dt, var=process_noise_var)
#     tracker.Q = block_diag(q, q)
#
#     # initialize measurement function (only x and y coordinates are measured)
#     tracker.H = np.array([[1, 0, 0, 0],
#                           [0, 0, 1, 0]])
#
#     # initialize measurement noise matrix in 2 D
#     tracker.R = np.array([[measurement_noise_var, 0],
#                           [0, measurement_noise_var]])
#
#     # initial conditions
#     tracker.x = np.array([[0, 0, 0, 0]]).T
#     # uncertainty of initial conditions
#     tracker.P = np.eye(4) * 500.
#
#     # initializing timer
#     x = 0
#     y = 0
#     vx = 0
#     vy = 0
#     t_last_predict = t_last_groundtruth = datetime.now()
#
#     while True:
#         # try to get element from queue
#         try:
#             od_element = od_position_queue.get_nowait()
#         except Empty:
#             od_element = None
#
#         if od_element is not None:
#             (tcap_str, tpush, pred_positions) = od_element
#             tcap = datetime.strptime(tcap_str, "%Y-%m-%d %H:%M:%S.%f")
#             xod, yod = pred_positions[0]
#             t_last_groundtruth = datetime.now()
#             logger.debug(f"Kalman process: received element from queue: {od_element}")
#
#         # check if time since last process run is greater than 1/process_freq
#         if (datetime.now() - t_last_predict).total_seconds() > 1 / process_freq:
#             # update tracker
#             # check if we have a ground truth value since last prediction by comparing t_last_predict and t_last_groundtruth
#             if (t_last_predict - t_last_groundtruth).total_seconds() >= 0:
#                 logger.debug(f"Kalman process: no ground truth value since last prediction, use prediction to further predict")
#                 tracker.predict()
#                 # logger.debug(f"Tracker update with x: {x}, y: {y}")
#                 # get predicted values
#                 (x, vx, y, vy) = tracker.x
#                 tracker.update(np.array([x, y]))
#             else:
#                 logger.debug(f"Kalman process: found ground truth value since last prediction, use ground truth value to further predict")
#                 # # since there is a delay we predict as many times as we have to given dt and tcap of ground truth values
#                 # logger.info(f"tcap: {tcap}, now: {datetime.now()}")
#                 # time_diff = (tcap - datetime.now()).total_seconds()
#                 # num_predictions = abs(int(time_diff * process_freq))
#                 # logger.info(f"Time difference between tcap and now: {time_diff}, number of predictions: {num_predictions}")
#                 # for i in range(num_predictions):
#                 #     tracker.predict()
#                 #     logger.info(f"predict: {tracker.x}")
#                 #     (x, vx, y, vy) = tracker.x
#                 #     if i==0:
#                 #         tracker.update(np.array([xod, xod]))
#                 #     else:
#                 #         tracker.update(np.array([x, y]))
#                 tracker.predict()
#                 (x, vx, y, vy) = tracker.x
#                 tracker.update(np.array([xod, yod]))
#                     # check if output queue is not None, if so push predicted values to output queue
#
#                 # logger.debug(f"Tracker update with xgt: {xod}, ygt: {yod}, predicted {num_predictions} times")
#                 # get predicted values
#                 # (x, vx, y, vy) = tracker.x
#
#             t_last_predict = datetime.now()
#             logger.debug(f"Kalman process: predicted values: x: {x}, y: {y}, vx: {vx}, vy: {vy}")
#
#             # check if output queue is not None, if so push predicted values to output queue
#             if output_queue is not None:
#                 logger.debug(f"Kalman process: output queue is not None, push predicted values to output queue")
#                 t_put = datetime.now()
#                 output_queue.put((t_put, [(x, y)]))
#             else:
#                 # logger.info([(x, y)])
#                 generate_pred_json([(x[0], y[0])])






