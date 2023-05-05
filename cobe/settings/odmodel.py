"""Settings of the object detection model trained on roboflow server"""
# api_key to be able to download model from roboflow server
api_key = "api_key"
# model name
model_name = "projekt_gesty"
# url of the background roboflow inference server container (with ending /)
inf_server_url = "http://localhost:9001/"
model_id = "/" + model_name
version = "2"
