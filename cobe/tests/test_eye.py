"""
    Testing the eye module of cobe.vision
    ======================================
"""
import multiprocessing
import unittest
import cobe.vision.eye as eye  # The module to test
from Pyro5.api import Proxy  # For testing the Pyro5 proxy
from time import sleep


class TestEye(unittest.TestCase):
    """ Testing the eye module of cobe.vision """

    def test_eye_return_id(self):
        """ Testing the return_id method of CoBeEye class"""
        # Create an instance of the class
        eye_instance = eye.CoBeEye()
        # Call the method
        returned_id = eye_instance.return_id()
        # Check the result
        self.assertEqual(returned_id, eye_instance.id)

    def test_eye_recalculate_id(self):
        """ Testing the recalculate_id method of CoBeEye class"""
        # Create an instance of the class
        eye_instance = eye.CoBeEye()
        # Get the id of the class
        old_id = eye_instance.id
        # recalculating the id
        eye_instance.recalculate_id()
        # the new od should be old + 2
        self.assertEqual(eye_instance.id, old_id + 2)

    def test_eye_return_secret_id(self):
        """ Testing the _return_secret_id method of CoBeEye class"""
        # without using Pyro5 this should return its secret id
        # Create an instance of the class
        eye_instance = eye.CoBeEye()
        # Call the method
        returned_secret_id = eye_instance._return_secret_id()
        # Check the result
        self.assertEqual(returned_secret_id, eye_instance.secret_id)

        # when we use Pyro5.api.Proxy, this should raise an AttributeError
        # Create an instance of the class with Pyro5
        with multiprocessing.Pool(processes=1) as pool:
            # start the daemon in a separate process with default settings
            pool.apply_async(eye.main)

            # Wait for the daemon to start
            sleep(0.5)

            # Create a Pyro5 proxy for the registered object
            uri = "PYRO:cobe.eye@localhost:9090"
            with Proxy(uri) as proxy:
                with self.assertRaises(AttributeError):
                    proxy._return_secret_id()
