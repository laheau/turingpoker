import torch
import torch.nn as nn
    
class ModelV1():
    def __init__(self, input_size, output_size, NN):
        super(ModelV1, self).__init__()

        self.fc = NN(input_size, output_size)
    
    def forward(self, x):
        return nn.Softmax(self.fc(x))
    
    def load_state(self, filename):
        self.load_state_dict(torch.load(f'{filename}.pth', weights_only=True))

NN = lambda h, o: nn.Sequential(
            nn.Linear(h, 1024),
            nn.ReLU(),
            nn.Linear(1024, 1024),
            nn.ReLU(),
            nn.Linear(1024, 256),
            nn.ReLU(),
            nn.Linear(256, o)
        )

NN2 = lambda h, o: nn.Sequential(
            nn.Linear(h, 1024),
            nn.ReLU(),
            nn.Linear(1024, 2048),
            nn.ReLU(),
            nn.Linear(2048, 1024),
            nn.ReLU(),
            nn.Linear(1024, 256),
            nn.ReLU(),
            nn.Linear(256, o)
        )