import torch
import torch.nn as nn
import math
import json
from baseline.model import Classifier, load_classifier_model, create_classifier_model
from baseline.pytorch.torchy import *
import torch.backends.cudnn as cudnn
cudnn.benchmark = True


class ConvModel(nn.Module, Classifier):

    def __init__(self):
        super(ConvModel, self).__init__()

    def save(self, outname):
        print('saving %s' % outname)
        torch.save(self, outname)

    def create_loss(self):
        return nn.NLLLoss()

    @staticmethod
    def load(outname, **kwargs):
        model = torch.load(outname)
        return model

    @staticmethod
    def create(embeddings, labels, **kwargs):
        pdrop = kwargs.get('dropout', 0.5)
        finetune = kwargs.get('finetune', True)
        filtsz = kwargs['filtsz']
        cmotsz = kwargs['cmotsz']
        dsz = embeddings.dsz
        model = ConvModel()
        model.labels = labels
        nc = len(labels)
        model.vocab = embeddings.vocab
        model.lut = nn.Embedding(embeddings.vsz + 1, dsz)
        del model.lut.weight
        model.lut.weight = nn.Parameter(torch.FloatTensor(embeddings.weights), requires_grad=finetune)
        convs = []
        for i, fsz in enumerate(filtsz):
            pad = fsz//2                
            conv = nn.Sequential(
                nn.Conv1d(dsz, cmotsz, fsz, padding=pad),
                pytorch_activation("relu")
            )
            convs.append(conv)
            # Add the module so its managed correctly
        model.convs = nn.ModuleList(convs)
        # Width of concat of parallel convs
        input_dim = cmotsz * len(filtsz)
        model.fconns = nn.Sequential()

        append2seq(model.fconns, (
            ##nn.BatchNorm1d(input_dim),
            nn.Dropout(pdrop),
            nn.Linear(input_dim, nc),
            nn.LogSoftmax()
        ))
        return model
    
    def forward(self, input):
        # BxTxC -> BxCxT
        embeddings = self.lut(input).transpose(1, 2).contiguous()
        mots = []
        for conv in self.convs:
            # In Conv1d, data BxCxT, max over time
            conv_out = conv(embeddings)
            mot, _ = conv_out.max(2)
            mots.append(mot.squeeze(2))

        mots = torch.cat(mots, 1)
        output = self.fconns(mots)
        return output

    def classify(self, batch_time):
        return classify_bt(self, batch_time)

    def get_labels(self):
        return self.labels

    def get_vocab(self):
        return self.vocab


def create_model(w2v, labels, **kwargs):
    return create_classifier_model(ConvModel.create, w2v, labels, **kwargs)


def load_model(outname, **kwargs):
    return load_classifier_model(ConvModel.load, outname, **kwargs)
