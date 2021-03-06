from __future__ import division, print_function

import os.path as osp

import torch
from torch import nn
from torch.autograd import Variable
import torch.nn.functional as F
from torch_scatter import scatter_max
from torch_geometric.datasets import ENZYMES
from torch_geometric.transform import TargetIndegreeAdj
from torch_geometric.utils import DataLoader
from torch_geometric.nn.modules import SplineConv
from torch_geometric.nn.functional.pool import graclus_pool

path = osp.join(osp.dirname(osp.realpath(__file__)), '..', 'data', 'ENZYMES')
train_dataset = ENZYMES(path, transform=TargetIndegreeAdj())
val_dataset = ENZYMES(path, transform=TargetIndegreeAdj())
test_dataset = ENZYMES(path, transform=TargetIndegreeAdj())
perm = torch.randperm(len(train_dataset))
split = len(train_dataset) // 10
train_dataset.split = perm[2 * split:]
val_dataset.split = perm[:split]
test_dataset.split = perm[split:2 * split]
train_loader = DataLoader(train_dataset, batch_size=64, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=64)
test_loader = DataLoader(test_dataset, batch_size=64)


class Net(nn.Module):
    def __init__(self):
        super(Net, self).__init__()
        self.conv1 = SplineConv(3, 32, dim=1, kernel_size=2)
        self.conv2 = SplineConv(32, 64, dim=1, kernel_size=2)
        self.conv3 = SplineConv(64, 128, dim=1, kernel_size=2)
        self.conv4 = SplineConv(128, 256, dim=1, kernel_size=2)
        self.conv5 = SplineConv(256, 512, dim=1, kernel_size=2)
        self.fc1 = nn.Linear(512, 256)
        self.fc2 = nn.Linear(256, 6)

    def forward(self, data):
        data.input = F.elu(self.conv1(data.input, data.index, data.weight))
        data = graclus_pool(data, transform=TargetIndegreeAdj())
        data.weight = Variable(data.weight)

        data.input = F.elu(self.conv2(data.input, data.index, data.weight))
        data = graclus_pool(data, transform=TargetIndegreeAdj())
        data.weight = Variable(data.weight)

        data.input = F.elu(self.conv3(data.input, data.index, data.weight))
        data = graclus_pool(data, transform=TargetIndegreeAdj())
        data.weight = Variable(data.weight)

        data.input = F.elu(self.conv4(data.input, data.index, data.weight))
        data = graclus_pool(data, transform=TargetIndegreeAdj())
        data.weight = Variable(data.weight)

        x = F.elu(self.conv5(data.input, data.index, data.weight))

        index = Variable(data.batch.unsqueeze(1).expand(x.size()))
        x, _ = scatter_max(index, x, dim=0)

        x = F.elu(self.fc1(x))
        x = F.dropout(x, training=self.training)
        return F.log_softmax(self.fc2(x), dim=1)


model = Net()
if torch.cuda.is_available():
    model = model.cuda()

optimizer = torch.optim.Adam(model.parameters(), lr=0.001)


def train(epoch):
    model.train()

    if epoch == 401:
        for param_group in optimizer.param_groups:
            param_group['lr'] = 0.0001

    for data in train_loader:
        data = data.cuda().to_variable()
        optimizer.zero_grad()
        output = model(data)
        loss = F.nll_loss(output, data.target)
        loss.backward()
        optimizer.step()


def test(dataset, loader):
    model.eval()
    correct = 0

    for data in loader:
        data = data.cuda().to_variable()
        pred = model(data).data.max(1)[1]
        correct += pred.eq(data.target.data).sum()
    return correct / len(dataset)


for epoch in range(1, 501):
    train(epoch)
    train_acc = test(train_dataset, train_loader)
    val_acc = test(val_dataset, val_loader)
    test_acc = test(test_dataset, test_loader)

    print('Epoch: {:03d}, Train: {:.4f}, Val: {:.4f}, Test: {:.4f}'.format(
        epoch, train_acc, val_acc, test_acc))
