import torch
from torch.nn import Module, Parameter
from torch_spline_conv import spline_conv

from .utils.inits import uniform
from .utils.repeat import repeat_to


class SplineConv(Module):
    """Spline-based Convolutional Operator :math:`(f \star g)(i) =
    1/|\mathcal{N}(i)| \sum_{l=1}^{M_{in}} \sum_{j \in \mathcal{N}(j)}
    f_l(j) \cdot g_l(u(i, j))`, where :math:`g_l` is a kernel function defined
    over the weighted B-Spline tensor product basis for a single input feature
    map. (Fey et al: SplineCNN: Fast Geometric Deep Learning with Continuous
    B-Spline Kernels, CVPR 2018, https://arxiv.org/abs/1711.08920)

    Args:
        in_channels (int): Size of each input sample.
        out_channels (int): Size of each output sample.
        dim (int): Pseudo-coordinate dimensionality.
        kernel_size (int or [int]): Size of the convolving kernel.
        is_open_spline (bool or [bool], optional): Whether to use open or
            closed B-spline bases. (default :obj:`True`)
        degree (int, optional): B-spline basis degrees. (default: :obj:`1`)
        root_weight (bool, optional): If set to :obj:`True`, the layer will
            add the weighted root node features to the output.
            (default: :obj:`True`)
        bias (bool, optional): If set to :obj:`False`, the layer will not learn
            an additive bias. (default: :obj:`True`)
    """

    def __init__(self,
                 in_channels,
                 out_channels,
                 dim,
                 kernel_size,
                 is_open_spline=True,
                 degree=1,
                 root_weight=True,
                 bias=True):

        super(SplineConv, self).__init__()

        self.in_channels = in_channels
        self.out_channels = out_channels
        self.degree = degree

        kernel_size = torch.LongTensor(repeat_to(kernel_size, dim))
        self.register_buffer('kernel_size', kernel_size)

        is_open_spline = torch.ByteTensor(repeat_to(is_open_spline, dim))
        self.register_buffer('is_open_spline', is_open_spline)

        weight = torch.Tensor(kernel_size.prod(), in_channels, out_channels)
        self.weight = Parameter(weight)

        if root_weight:
            root_weight = torch.Tensor(in_channels, out_channels)
            self.root_weight = Parameter(root_weight)
        else:
            self.register_parameter('root_weight', None)

        if bias:
            self.bias = Parameter(torch.Tensor(out_channels))
        else:
            self.register_parameter('bias', None)

        self.reset_parameters()

    def reset_parameters(self):
        size = self.in_channels * self.weight.size(0)
        uniform(size, self.weight)
        uniform(size, self.root_weight)
        uniform(size, self.bias)

    def forward(self, x, edge_index, pseudo):
        return spline_conv(x, edge_index, pseudo, self.weight,
                           self._buffers['kernel_size'],
                           self._buffers['is_open_spline'], self.degree,
                           self.root_weight, self.bias)
