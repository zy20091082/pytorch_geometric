import torch
from torch_geometric.read import parse_txt
from torch_geometric.data import Data
from torch_geometric.utils import face_to_edge_index


def parse_off(src):
    counts_line = src[1].split()
    num_nodes, num_faces = int(counts_line[0]), int(counts_line[1])

    pos = parse_txt(src[2:2 + num_nodes])

    face = src[2 + num_nodes:2 + num_nodes + num_faces]
    face = parse_txt(face, start=1, out=torch.LongTensor())

    edge_index = face_to_edge_index(face, pos.size(0))

    data = Data(edge_index=edge_index, pos=pos)
    data.face = face

    return data


def read_off(path):
    with open(path, 'r') as f:
        src = f.read().split('\n')[:-1]
    return parse_off(src)
