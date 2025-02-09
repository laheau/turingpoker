import torch
choices = torch.tensor([3, 4, 5, 5 ,3])
targets = torch.nn.functional.one_hot(choices, 22)

print(targets.shape)

print(targets)
