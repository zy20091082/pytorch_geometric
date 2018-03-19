import os
import sys
import random
import numpy as np
import torch
from torch import nn
import torch.nn.functional as F
from torchvision.transforms import Compose

sys.path.insert(0, '.')
sys.path.insert(0, '..')



from torch_geometric.datasets import ModelNet10RandAugPC  # noqa
from torch_geometric.utils import DataLoader2  # noqa
from torch_geometric.transform import (NormalizeScale, RandomFlip,
                                       CartesianAdj, RandomTranslate,
                                       PCToGraphNN, PCToGraphRad,
                                       SamplePointcloud, RandomRotate)  # noqa
from torch_geometric.nn.modules import InvGraphConv  # noqa
from torch.nn import Linear as Lin # noqa
from torch_geometric.nn.functional import (sparse_voxel_max_pool,
                                           dense_voxel_max_pool)  # noqa
from torch_geometric.visualization.model import show_model  # noqa

path = os.path.dirname(os.path.realpath(__file__))
path = os.path.join(path, '..', 'data', 'ModelNet10RandAugPC')

to_graph = PCToGraphNN()
#to_graph = PCToGraphRad(r=0.03)
transform = CartesianAdj()
init_transform = Compose([SamplePointcloud(num_points=2048), NormalizeScale(),
                          to_graph])
train_dataset = ModelNet10RandAugPC(path, True, transform=init_transform)
test_dataset = ModelNet10RandAugPC(path, False, transform=init_transform)
batch_size = 6
train_loader = DataLoader2(train_dataset, batch_size=batch_size, shuffle=True)
test_loader = DataLoader2(test_dataset, batch_size=batch_size)

class Net(nn.Module):
    def __init__(self):
        super(Net, self).__init__()
        self.conv1 = InvGraphConv(1, 8, dim=3, kernel_size=5)
        self.conv2 = InvGraphConv(17, 16, dim=3, kernel_size=5)
        self.conv3 = InvGraphConv(25, 24, dim=3, kernel_size=5)
        self.conv4 = InvGraphConv(33, 32, dim=3, kernel_size=5)
        self.conv5 = InvGraphConv(41, 40, dim=3, kernel_size=5)
        self.fc1 = nn.Linear(8 * 49, 10)

        self.att1 = Lin(32, 2)
        self.att2 = Lin(64, 2)
        self.att3 = Lin(64, 2)
        self.att4 = Lin(64, 2)

    def pool_args(self, mean, x):
        if not self.training:
            return 1 / mean, 0
        size = [1 / random.uniform(mean - x, mean + x) for _ in range(3)]
        # size = 1 / mean
        start = [random.uniform(-1 / (mean - x), 0) for _ in range(3)]
        # start = 0
        return size, start

    def forward(self, data):
        data.input = self.conv1(data.adj, data.input)
        # att1 = self.att1(data.input)
        size, start = self.pool_args(32, 8)
        data, _ = sparse_voxel_max_pool(data, size, start, transform)

        data.input = self.conv2(data.adj, data.input)

        # att2 = self.att2(data.input)
        size, start = self.pool_args(16, 4)
        data, _ = sparse_voxel_max_pool(data, size, start, transform)

        data.input = self.conv3(data.adj, data.input)
        # att3 = self.att3(data.input)
        size, start = self.pool_args(8, 2)
        data, _ = sparse_voxel_max_pool(data, size, start, transform)

        data.input = self.conv4(data.adj, data.input)
        # att4 = self.att4(data.input)
        size, start = self.pool_args(4, 1)
        data, _ = sparse_voxel_max_pool(data, size, start, transform)

        data.input = self.conv5(data.adj, data.input)
        data, _ = dense_voxel_max_pool(data, 1, -0.5, 1.5)

        x = data.input.view(-1, self.fc1.weight.size(1))
        x = F.dropout(x, training=self.training)
        x = self.fc1(x)

        return F.log_softmax(x, dim=1)


model = Net()
if torch.cuda.is_available():
    model.cuda()

optimizer = torch.optim.Adam(model.parameters(), lr=0.01)



def train(epoch):
    model.train()

    if epoch == 11:
        for param_group in optimizer.param_groups:
            param_group['lr'] = 0.0005

    if epoch == 21:
        for param_group in optimizer.param_groups:
            param_group['lr'] = 0.0001

    if epoch == 31:
        for param_group in optimizer.param_groups:
            param_group['lr'] = 0.00005

    if epoch == 41:
        for param_group in optimizer.param_groups:
            param_group['lr'] = 0.00001

    for data in train_loader:
        data = data.cuda().to_variable(['input', 'target', 'pos'])
        optimizer.zero_grad()
        data = transform(data)
        loss = F.nll_loss(model(data), data.target)
        loss.backward()
        optimizer.step()
        #to_graph.r = model.transform.r.data.clamp(min=0.0001, max=1)[0]


def test(epoch, loader, dataset, str):
    model.eval()
    correct = 0
    false_per_class = np.zeros(10)
    examples_per_class = np.zeros(10)

    for data in loader:
        data = data.cuda().to_variable(['input', 'pos'])
        data = transform(data)
        pred = model(data).data.max(1)[1]
        eq = pred.eq(data.target).cpu()
        false = (1-eq).nonzero()
        false = false.view(-1)
        if false.dim() > 0:
            uniques, fpc = np.unique(data.target.cpu()[false].numpy(),
                               return_counts=True)
            false_per_class[uniques] += fpc
        uniques_epc, epc = np.unique(data.target.cpu().numpy(),
                                 return_counts=True)
        examples_per_class[uniques_epc] += epc
        correct += eq.sum()



    accuracy_per_class = (examples_per_class-false_per_class)/examples_per_class
    np.set_printoptions(precision=4)
    print('Epoch:', epoch, str, 'Accuracy:', correct / len(dataset))
    print(accuracy_per_class, 'Class Accuracy:',accuracy_per_class.mean())
    print(false_per_class)


#test(0, train_loader, train_dataset, 'Train')
#test(0, test_loader, test_dataset, 'Test')
for epoch in range(1, 51):
    train(epoch)
    test(epoch, train_loader, train_dataset, 'Train')
    test(epoch, test_loader, test_dataset, 'Test')