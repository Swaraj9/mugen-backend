import torch
from torch import nn
import music21
import glob
import numpy as np
import os
import uuid
import sys

duration = int(sys.argv[1])
genre = int(sys.argv[2])

def loadMidiFile(file):
    return music21.converter.parse(file)

class MIDI():
    def __init__(self, seq_length, transpose=False):
        self.seq_length = seq_length
        self.file_notes = []
        self.file_durations = []
        self.trainseq = []
        self.duraseq = []
        self.transfer_dic = dict()
        self.dic_n = 0
        self.transpose = transpose

    def parser(self, folderName):
        """ Get all the rests and notes and chords from the midi files """
        
        bar = glob.glob(f"{folderName}/*.mid")
        for file in bar:
            midi = loadMidiFile(file)
            
            if self.transpose:
                k = midi.analyze('key')
                i = music21.interval.Interval(k.tonic, music21.pitch.Pitch('C'))
                midi = midi.transpose(i)
            
            notes = []
            durations = []

            for element in midi.flatten():    
                if isinstance(element, music21.chord.Chord):
                    #notes.append('.'.join(n.nameWithOctave for n in element.pitches))
                    notes.append(element.pitches[-1].name)
                    durations.append(element.duration.quarterLength)

                if isinstance(element, music21.note.Note):
                    if element.isRest:
                        notes.append(str(element.name))
                        durations.append(element.duration.quarterLength)
                    else:
                        notes.append(str(element.nameWithOctave))
                        durations.append(element.duration.quarterLength)   

            self.file_notes.append(notes)
            self.file_durations.append([min(float(i), 1) for i in durations])
        note_set = sorted(set(note for notes in self.file_notes for note in notes))
        self.dic_n = len(note_set)
        # A dictionary to map notes, chords and rest to integers
        self.transfer_dic = dict((note, number) for number, note in enumerate(note_set))

    def prepare_sequences(self):
        """ Prepare the sequences used by the Neural Network """
        self.trainseq = []
        self.duraseq = []

        # create input sequences and the corresponding outputs
        for notes, durations in zip(self.file_notes, self.file_durations):
            for i in range(len(notes) - self.seq_length):
                self.trainseq.append([self.transfer_dic[note] for note in notes[i:i + self.seq_length]])
                self.duraseq.append(durations[i:i + self.seq_length])

        # Normalize sequences between -1 and 1
        self.trainseq = torch.Tensor(self.trainseq)
        self.trainseq = (self.trainseq - float(self.dic_n) / 2) / (float(self.dic_n) / 2)
        self.duraseq = torch.Tensor(self.duraseq)
        self.trainseq = torch.cat((self.trainseq, self.duraseq), 1)

        return self.trainseq
    
midi = MIDI(seq_length=duration, transpose=True)
if genre==0:
    midi.parser("../python/bach")
elif genre==1:
    midi.parser("../python/lofi")
elif genre==2:
    midi.parser("../python/jazz")

    
def generate(name, generator):
    # random noise for network input
    noise = torch.autograd.Variable(torch.Tensor(np.random.normal(0, 1, (128, 100))))
    noise_durations = torch.autograd.Variable(torch.Tensor(np.random.normal(0, 1, (128, 100))))
    predictions, pred_durations = generator(noise, noise_durations)

    # transfer sequence numbers to notes
    boundary = int(len(midi.transfer_dic) / 2)
    pred_nums = [x * boundary + boundary for x in predictions[63]]
    notes = [key for key in midi.transfer_dic]
    pred_notes = [notes[int(x)] for x in pred_nums]
    pred_durations = pred_durations[63].detach().cpu().numpy()

    # create Result directory if there isn't exist
    if not os.path.exists('Result/'):
      os.makedirs('Result/')

    def create_midi(pred_notes, pred_durations, filename):
        """ convert the output from the prediction to notes and create a midi file
        from the notes """
        offset = 0
        midi_stream = music21.stream.Stream()

        # create note and chord objects based on the values generated by the model
        for pattern, duration in zip(pred_notes, pred_durations):
            # rest
            if pattern == 'R':
                midi_stream.append(music21.note.Rest())
            # chord
            elif ('.' in pattern) or pattern.isdigit():
                notes_in_chord = pattern.split('.')
                notes = []
                for current_note in notes_in_chord:
                    new_note = music21.note.Note(current_note)
                    new_note.duration.quarterLength = duration+1
                    new_note.storedInstrument = music21.instrument.Piano()
                    notes.append(new_note)
                new_chord = music21.chord.Chord(notes)
                new_chord.offset = offset
                midi_stream.append(new_chord)
            # note
            else:
                new_note = music21.note.Note(pattern)
                new_note.duration.quarterLength = duration + 1
                new_note.offset = offset
                new_note.storedInstrument = music21.instrument.Piano()
                midi_stream.append(new_note)

            # increase offset each iteration so that notes do not stack
            offset += 0.25

        # midi_stream.show('text')
        midi_stream.write('midi', fp=f'{filename}.midi')

    # generate music with .midi format
    create_midi(pred_notes, pred_durations, f'Result/{name}')


class Generator(nn.Module):
    def __init__(self):
        super(Generator, self).__init__()

        def block(in_feat, out_feat, normalize=True):
            layers = [nn.Linear(in_feat, out_feat)]
            if normalize:
                layers.append(nn.BatchNorm1d(out_feat, 0.8))
            layers.append(nn.LeakyReLU(0.2, inplace=True))
            return layers

        self.left = nn.Sequential(
            *block(256, 1),
            *block(1, 256),
        )
        self.lstm = nn.LSTM(200, 256, 2, batch_first=False)
        self.bilstm_1 = nn.LSTM(256, 256, 2, bidirectional=True, batch_first=False)
        self.bilstm_2 = nn.LSTM(256, 256, 2, bidirectional=True, batch_first=False)
        self.relu = nn.ReLU(inplace=False)
        
        self.reshape = nn.Linear(512, 200)
        
        self.LeakyReLU = nn.LeakyReLU(0.2, inplace=False)
        self.tanh = nn.Tanh()
        self.dense_1 = nn.Linear(512, 256)
        self.dense_2 = nn.Linear(512, 256)
        self.dense_512 = nn.Linear(256, 512)
        self.dense_1024 = nn.Linear(256, 1024)

    def forward(self, notes, durations):
        x = torch.cat((notes,durations), 1)
        a, _ = self.lstm(x)
        a, _ = self.bilstm_1(a) #1
        a = self.dense_1(a)
        a = self.LeakyReLU(a)
        a, _ = self.bilstm_2(a)
        a = self.dense_2(a)
        a = self.LeakyReLU(a)
        a = self.dense_512(a)
        a = self.LeakyReLU(a)      
#         b = self.left(a)
#         c = a * b
        c = self.reshape(a)
        notes, durations = torch.split(c, 100, 1)
        notes = self.tanh(notes)
        durations = self.relu(durations)
        return notes, durations

generator = Generator()
generator.load_state_dict(torch.load("../models/generator.pt", map_location=torch.device("cpu")))
generator.eval()

fileName = uuid.uuid4()
generate(fileName, generator)
print(fileName, end="")