import helloworld_pb2
import helloworld_pb2_grpc
import grpc
from concurrent import futures
import time
import unittest

class Greeter(helloworld_pb2_grpc.GreeterServicer):
    def SayHello(self, request, context):
        return helloworld_pb2.HelloReply(message=f"Hello, {request.name}!")

class TestGRPCBasic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
        helloworld_pb2_grpc.add_GreeterServicer_to_server(Greeter(), cls.server)
        cls.port = 50051
        cls.server.add_insecure_port(f'[::]:{cls.port}')
        cls.server.start()
        time.sleep(0.5)  # Wait for server to start

    @classmethod
    def tearDownClass(cls):
        cls.server.stop(0)

    def test_say_hello(self):
        channel = grpc.insecure_channel(f'localhost:{self.port}')
        stub = helloworld_pb2_grpc.GreeterStub(channel)
        response = stub.SayHello(helloworld_pb2.HelloRequest(name='World'))
        self.assertEqual(response.message, 'Hello, World!')

if __name__ == '__main__':
    unittest.main()